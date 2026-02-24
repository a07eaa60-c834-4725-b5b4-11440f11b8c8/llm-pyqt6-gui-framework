# nvidia_nim_service.py
import os
from openai import OpenAI
from core.services.base_service import BaseAIService, BaseAIWorker

class NvidiaNimWorker(BaseAIWorker):
    """
    Worker thread to handle streaming API calls to NVIDIA NIM via OpenAI SDK.
    """
    def __init__(self, client, model_name, messages, enable_thinking=True):
        super().__init__()
        self.client = client
        self.model_name = model_name
        self.messages = messages
        self.enable_thinking = enable_thinking

    def run(self):
        try:
            # Build request parameters
            request_params = {
                "model": self.model_name,
                "messages": self.messages,
                "stream": True
            }
            
            # Add thinking parameter for models that support it (DeepSeek, Kimi K2)
            # Per NVIDIA NIM docs: must be wrapped in chat_template_kwargs
            if self.enable_thinking:
                request_params["extra_body"] = {"chat_template_kwargs": {"thinking": True}}
            
            # Use streaming API
            response_stream = self.client.chat.completions.create(**request_params)
            
            full_response = ""
            full_thinking = ""
            
            for chunk in response_stream:
                if self._is_cancelled:
                    break
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    # Check for reasoning content (DeepSeek, Kimi K2 format)
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        self.thinking_chunk.emit(delta.reasoning_content)
                        full_thinking += delta.reasoning_content
                    
                    # Regular content
                    if hasattr(delta, 'content') and delta.content:
                        self.chunk.emit(delta.content)
                        full_response += delta.content
            
            if self._is_cancelled:
                self.error.emit("Generation interrupted by user.")
                return

            self._emit_result(full_response, full_thinking)

        except Exception as e:
            self.error.emit(str(e))

class NvidiaNimService(BaseAIService):
    """Service for interacting with NVIDIA NIM API using OpenAI SDK."""

    # Model mapping: GUI friendly name -> API model ID
    MODEL_MAP = {
        "DeepSeek V3.2": "deepseek-ai/deepseek-v3.2",
        "Kimi K2": "moonshotai/kimi-k2-thinking"
    }

    def __init__(self):
        super().__init__()
        self.api_key = os.environ.get("NVIDIA_NIM_API_KEY")
        self.client = None

        if self.api_key:
            try:
                # Initialize OpenAI client with NVIDIA NIM base URL
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://integrate.api.nvidia.com/v1"
                )
            except Exception as e:
                print(f"Failed to initialize NVIDIA NIM Client: {e}")
        else:
            print("Warning: NVIDIA_NIM_API_KEY environment variable not set.")
            print("NVIDIA NIM service will be unavailable until API key is configured.")

    def _emit_error(self, message: str):
        self.status_updated.emit(f"Error: {message}")
        self.error_occurred.emit(message)

    def generate_response(self, system_prompt: str, user_input: str, model_name: str = "DeepSeek V3.2", conversation_history: list = None, **kwargs):
        """Generates a response using the NVIDIA NIM API in a background thread."""
        if not self.client:
            return self._emit_error("NVIDIA_NIM_API_KEY not found.")
        if not user_input.strip():
            return self._emit_error("Input cannot be empty.")

        api_model = self.MODEL_MAP.get(model_name, "deepseek-ai/deepseek-v3.2")
        self.status_updated.emit(f"Generating response using NVIDIA NIM {model_name}...")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            messages.extend([{"role": m.get("role", ""), "content": m.get("content", "")} for m in conversation_history if m.get("content")])
        messages.append({"role": "user", "content": user_input})

        worker = NvidiaNimWorker(self.client, api_model, messages, enable_thinking=True)
        self._start_worker(worker)