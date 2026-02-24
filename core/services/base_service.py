# core/services/base_service.py
from PyQt6.QtCore import QObject, pyqtSignal, QThread

class BaseAIWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    chunk = pyqtSignal(str)
    thinking_chunk = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _emit_result(self, full_response: str, full_thinking: str):
        """Emit combined thinking+response result or error if empty."""
        if full_response or full_thinking:
            combined = f"<thinking>\n{full_thinking}\n</thinking>\n\n" if full_thinking else ""
            self.finished.emit(combined + full_response)
        else:
            self.error.emit("API returned empty response.")

class BaseAIService(QObject):
    """Abstract base class establishing the interface for AI Services."""
    response_generated = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    chunk_received = pyqtSignal(str)
    thinking_chunk_received = pyqtSignal(str)
    stream_complete = pyqtSignal(str)

    def generate_response(self, system_prompt: str, user_input: str, model_name: str, conversation_history: list = None, **kwargs):
        raise NotImplementedError("generate_response must be implemented by subclasses.")

    def _start_worker(self, worker: BaseAIWorker):
        self.worker = worker
        self.worker.finished.connect(self._handle_success)
        self.worker.finished.connect(self.stream_complete.emit)
        self.worker.error.connect(self._handle_error)
        self.worker.chunk.connect(self.chunk_received.emit)
        self.worker.thinking_chunk.connect(self.thinking_chunk_received.emit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        if hasattr(self.worker, 'retry_with_new_key'):
            self.worker.retry_with_new_key.connect(getattr(self, '_handle_retry', lambda e, c: None))
            self.worker.retry_with_new_key.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_success(self, response_text: str):
        self.response_generated.emit(response_text)
        self.status_updated.emit("Response received.")

    def _handle_error(self, error_message: str):
        self.status_updated.emit(f"API Error: {error_message}")
        self.error_occurred.emit(error_message)

    def cancel_generation(self):
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.cancel()
