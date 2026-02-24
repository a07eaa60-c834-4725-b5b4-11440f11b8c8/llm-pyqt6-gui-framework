import os
import base64
from PyQt6.QtCore import pyqtSignal
from google import genai
from google.genai import types
from core.services.base_service import BaseAIService, BaseAIWorker

SAFETY_CATEGORIES = [
    "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_DANGEROUS_CONTENT",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_HARASSMENT",
]


class GeminiWorker(BaseAIWorker):
    """Worker thread to handle streaming API calls to Google Gemini."""
    retry_with_new_key = pyqtSignal(str, int)

    def __init__(self, client, model_name, contents, config, attempt_count=0):
        super().__init__()
        self.client = client
        self.model_name = model_name
        self.contents = contents
        self.config = config
        self.attempt_count = attempt_count

    def run(self):
        try:
            response_stream = self.client.models.generate_content_stream(
                model=self.model_name, contents=self.contents, config=self.config
            )
            full_response, full_thinking = "", ""

            for chunk in response_stream:
                if self._is_cancelled:
                    break
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'content') and candidate.content:
                            for part in candidate.content.parts:
                                if hasattr(part, 'thought') and part.thought and hasattr(part, 'text') and part.text:
                                    self.thinking_chunk.emit(part.text)
                                    full_thinking += part.text
                                elif hasattr(part, 'text') and part.text:
                                    self.chunk.emit(part.text)
                                    full_response += part.text
                elif hasattr(chunk, 'text') and chunk.text:
                    self.chunk.emit(chunk.text)
                    full_response += chunk.text

            if self._is_cancelled:
                self.error.emit("Generation interrupted by user.")
                return

            self._emit_result(full_response, full_thinking)

        except Exception as e:
            error_message = str(e)
            if "429" in error_message or "rate limit" in error_message.lower():
                self.retry_with_new_key.emit(error_message, self.attempt_count)
            else:
                self.error.emit(error_message)


class GeminiService(BaseAIService):
    """Service for interacting with Google Gemini API using google-genai SDK."""

    MODEL_MAP = {"Flash": "gemini-2.5-flash", "Pro": "gemini-2.5-pro"}
    MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB

    def __init__(self):
        super().__init__()
        self.api_keys = []
        self.current_key_index = 0
        self.rotation_attempts = 0
        self.client = None
        self._pending_request = None

        rotate_keys = os.environ.get("GEMINI_ROTATE_API_KEY")
        single_key = os.environ.get("GEMINI_API_KEY")
        if rotate_keys:
            self.api_keys = [k.strip() for k in rotate_keys.split(",") if k.strip()]
        elif single_key:
            self.api_keys = [single_key]

        if self.api_keys:
            try:
                self.client = genai.Client(api_key=self.api_keys[0])
            except Exception as e:
                print(f"Failed to initialize Gemini Client: {e}")

    def _emit_error(self, message: str):
        """Emit error to both status and error signals, clear pending request."""
        self.status_updated.emit(f"Error: {message}")
        self.error_occurred.emit(message)
        self._pending_request = None

    def _build_and_start(self):
        """Build request from pending parameters and start worker."""
        if not self._pending_request or not self.client:
            return

        params = self._pending_request
        files_data = params.get('files_data')
        user_input = params['user_input']

        if not user_input.strip() and not files_data:
            return self._emit_error("Input cannot be empty.")

        if files_data:
            for fd in files_data:
                if fd.get('file_size', 0) > self.MAX_FILE_SIZE:
                    return self._emit_error(f"File '{fd.get('filename', 'Unknown')}' too large. Maximum size: 15MB.")

        # Build conversation history
        contents = []
        for msg in (params.get('conversation_history') or []):
            role, content = msg.get("role", ""), msg.get("content", "")
            if not content:
                continue
            api_role = "model" if role == "assistant" else "user"
            try:
                contents.append(types.Content(role=api_role, parts=[types.Part.from_text(text=content)]))
            except Exception:
                contents.append({"role": api_role, "parts": [{"text": content}]})

        # Build current message parts
        current_parts = []
        if files_data:
            for fd in files_data:
                try:
                    if b64 := fd.get('base64'):
                        current_parts.append(types.Part.from_bytes(
                            data=base64.b64decode(b64),
                            mime_type=fd.get('mime_type', 'application/octet-stream')
                        ))
                except Exception as e:
                    return self._emit_error(f"Error processing file '{fd.get('filename', 'Unknown')}': {e}")

        if user_input.strip():
            current_parts.append(types.Part.from_text(text=user_input))
        if current_parts:
            contents.append(types.Content(role="user", parts=current_parts))

        config = types.GenerateContentConfig(
            system_instruction=params['system_prompt'],
            safety_settings=[types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in SAFETY_CATEGORIES],
            thinking_config=types.ThinkingConfig(include_thoughts=True, thinking_budget=8192)
        )

        api_model = self.MODEL_MAP.get(params['model_name'], "gemini-2.5-flash")
        self._start_worker(GeminiWorker(self.client, api_model, contents, config, self.rotation_attempts))

    def generate_response(self, system_prompt, user_input, model_name="Flash",
                          conversation_history=None, files_data=None):
        """Generate a response using the Gemini API in a background thread."""
        self.rotation_attempts = 0
        if self.api_keys:
            self.current_key_index = 0

        if not self.client:
            msg = "No Gemini API keys configured." if not self.api_keys else "Failed to initialize Gemini client."
            return self._emit_error(msg)

        self._pending_request = {
            'system_prompt': system_prompt, 'user_input': user_input,
            'model_name': model_name, 'conversation_history': conversation_history,
            'files_data': files_data
        }
        self.status_updated.emit(f"Generating response using {model_name}...")
        self._build_and_start()

    def _handle_success(self, response_text: str):
        super()._handle_success(response_text)
        self._pending_request = None

    def _handle_error(self, error_message: str):
        super()._handle_error(error_message)
        self._pending_request = None

    def _handle_retry(self, error_message: str, attempt_count: int):
        """Handle retry on 429 errors by rotating API keys."""
        if not self._pending_request:
            return self._emit_error(error_message)

        if len(self.api_keys) <= 1:
            return self._emit_error("All API keys rate limited.")

        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.rotation_attempts += 1
        self.status_updated.emit(f"API Key Rate Limited. Rotating to next key (attempt {attempt_count + 1})...")

        try:
            self.client = genai.Client(api_key=self.api_keys[self.current_key_index])
        except Exception:
            return self._emit_error("Failed to recreate client with new API key.")

        self._build_and_start()