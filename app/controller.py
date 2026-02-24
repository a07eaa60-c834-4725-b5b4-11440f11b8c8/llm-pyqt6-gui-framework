# app/controller.py
"""Application Controller - Orchestrates application logic and connects GUI to services."""
import sys
import base64
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import pyqtSignal, QObject, QTimer

from gui.main_window import MainWindow
from core.config import ConfigManager
from core.services.file_service import FileService
from core.services.gemini_service import GeminiService
from core.services.nvidia_nim_service import NvidiaNimService
from core.services.chat_history_service import ChatHistoryService

DARK_MSGBOX_STYLE = """
    QMessageBox, QLabel { background-color: #1a1a1a; color: #ffffff; }
    QPushButton { background-color: #3d3d3d; color: #ffffff; border: 1px solid #333; padding: 8px; border-radius: 4px; }
    QPushButton:hover { background-color: #4d4d4d; }
"""


class ApplicationController(QObject):
    """Orchestrates the application logic, connecting GUI signals to backend services."""
    append_user_message_signal = pyqtSignal(str, object)
    clear_input_signal = pyqtSignal()
    clear_response_signal = pyqtSignal()

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = ConfigManager()

        self.file_service = FileService()
        self.services = {"Gemini": GeminiService(), "NVIDIA NIM": NvidiaNimService()}
        self.chat_history_service = ChatHistoryService()

        self.selected_service = getattr(self.config_manager, "current_service", "Gemini")
        self.selected_model = getattr(self.config_manager, "current_model", "Flash")

        self.main_window = MainWindow(self.file_service)
        self.main_window.config_manager = self.config_manager

        for service in self.services.values():
            service.response_generated.connect(self._handle_ai_response)
            service.status_updated.connect(self.main_window.status_signal.emit)
            service.chunk_received.connect(self._handle_stream_chunk)
            service.thinking_chunk_received.connect(self._handle_thinking_chunk)
            service.stream_complete.connect(self._handle_stream_complete)
            service.error_occurred.connect(self._handle_generation_error)

        self._is_streaming = False
        self._is_generating = False

        self.chat_history_service.chat_loaded.connect(self._handle_chat_loaded)
        self._connect_signals()
        self._initialize_ui()

    def _connect_signals(self):
        abp = self.main_window.action_buttons_panel
        ip = self.main_window.input_panel

        abp.select_file_signal.connect(self.handle_select_file)
        abp.send_signal.connect(self.handle_send)
        abp.interrupt_signal.connect(self.handle_interrupt)
        abp.service_model_selected_signal.connect(self.handle_service_model_selected)
        abp.new_chat_signal.connect(self.handle_new_chat)
        abp.delete_chat_signal.connect(self.handle_delete_chat)
        abp.delete_all_chats_signal.connect(self.handle_delete_all_chats)
        abp.navigate_left_signal.connect(self.handle_navigate_left)
        abp.navigate_right_signal.connect(self.handle_navigate_right)

        ip.send_signal.connect(self.handle_send)
        ip.navigate_left_signal.connect(self.handle_navigate_left)
        ip.navigate_right_signal.connect(self.handle_navigate_right)

        self.append_user_message_signal.connect(self.main_window.response_panel.append_user_message)
        self.clear_input_signal.connect(lambda: ip.set_input_text(""))
        self.clear_response_signal.connect(self.main_window.response_panel.clear)

    def _initialize_ui(self):
        self._update_service_model_button_label()
        self.chat_history_service.create_new_chat()
        self._update_navigation_buttons()

    def run(self):
        self.main_window.resize(self.config_manager.window_width, self.config_manager.window_height)
        self.main_window.show()
        sys.exit(self.app.exec())

    # --- Action Handlers ---

    def handle_select_file(self, b64_data: str, filename: str):
        if not self.file_service.has_files():
            self.update_status("No files selected.")

    def handle_interrupt(self):
        if self._is_generating:
            self.update_status("Interrupting generation...")
            active_service = self._get_active_service()
            if hasattr(active_service, 'cancel_generation'):
                active_service.cancel_generation()

    def handle_send(self):
        user_input = self.get_input_text()
        if not user_input.strip() and not self.file_service.has_files():
            return self.update_status("Error: Input cannot be empty.")
        self._process_message(user_input)

    def handle_service_model_selected(self, service: str, model: str):
        self.selected_service = service
        self.selected_model = model
        self.config_manager.current_service = service
        self.config_manager.current_model = model
        self.config_manager.save()
        self._update_service_model_button_label()
        self.update_status(f"Selected: {service} - {model}")

    def handle_new_chat(self):
        if self._is_generating:
            return self.update_status("Cannot create a new chat while generating.")
        if self.chat_history_service.get_current_messages():
            self.chat_history_service.save_current_chat()
        self.chat_history_service.create_new_chat()
        self.clear_response_signal.emit()
        self.clear_input_signal.emit()
        self.update_status("New chat created.")
        self._update_navigation_buttons()

    def handle_delete_chat(self):
        if self._is_generating:
            return self.update_status("Cannot delete chat while generating.")
        current_chat_id = self.chat_history_service.get_current_chat_id()
        if not current_chat_id:
            return self.update_status("No chat to delete.")
        if not self._confirm_dialog("Delete Chat", "Are you sure you want to delete this chat?"):
            return

        if self.chat_history_service.delete_chat(current_chat_id):
            adjacent_id = (self.chat_history_service.get_adjacent_chat_id("left") or
                           self.chat_history_service.get_adjacent_chat_id("right"))
            if adjacent_id:
                self.chat_history_service.load_chat(adjacent_id)
                self.update_status(f"Chat deleted. Loaded chat: {adjacent_id}")
            else:
                self.chat_history_service.create_new_chat()
                self.clear_response_signal.emit()
                self.update_status("Chat deleted. New chat created.")
        else:
            self.update_status("Failed to delete chat.")
        self._update_navigation_buttons()

    def handle_delete_all_chats(self):
        if self._is_generating:
            return self.update_status("Cannot delete all chats while generating.")
        chat_files = self.chat_history_service.get_chat_files()
        if not chat_files:
            return self.update_status("No chats to delete.")
        if not self._confirm_dialog("Delete All Chats", f"Are you sure you want to delete all {len(chat_files)} chats?"):
            return

        if self.chat_history_service.delete_all_chats():
            self.chat_history_service.clear_current_chat()
            self.chat_history_service.create_new_chat()
            self.clear_response_signal.emit()
            self.update_status("All chats deleted. New chat created.")
        else:
            self.update_status("Failed to delete some chats.")
        self._update_navigation_buttons()

    def handle_navigate_left(self):
        self._handle_navigation("left")

    def handle_navigate_right(self):
        self._handle_navigation("right")

    # --- Internal Logic ---

    def _process_message(self, user_input: str):
        if self._is_generating:
            return self.update_status("Please wait for the current response to finish.")

        has_files = self.file_service.has_files()
        if not self.chat_history_service.get_current_chat_id():
            self.chat_history_service.create_new_chat()

        file_data_list, filenames_list = [], None
        if has_files:
            for file_b64, filename in self.file_service.get_files():
                file_data_list.append({
                    'base64': file_b64, 'filename': filename,
                    'mime_type': self._get_mime_type(filename),
                    'file_size': len(base64.b64decode(file_b64))
                })
            if file_data_list:
                filenames_list = [f['filename'] for f in file_data_list]

        display_text = user_input or (
            f"Process file{'s' if len(file_data_list) > 1 else ''}: {', '.join(filenames_list)}"
            if filenames_list else ""
        )

        self.append_user_message_signal.emit(display_text, filenames_list)
        self.chat_history_service.add_message("user", display_text, filenames_list)
        self.clear_input_signal.emit()

        active_service = self._get_active_service()
        self._set_generating_state(True)

        kwargs = {}
        if self.selected_service == "Gemini" and file_data_list:
            kwargs['files_data'] = file_data_list

        active_service.generate_response(
            self.config_manager.default_system_prompt, user_input,
            self.selected_model, self.chat_history_service.get_current_messages()[:-1], **kwargs
        )

        if has_files:
            self.file_service.clear_files()

    def _handle_ai_response(self, response_text: str):
        if not self._is_streaming:
            self.main_window.response_panel.append_assistant_message(response_text)
        self.chat_history_service.add_message("assistant", response_text)
        if chat_id := self.chat_history_service.save_current_chat():
            self.update_status(f"Chat saved: {chat_id}")
        self._is_streaming = False
        self._set_generating_state(False)

    def _handle_generation_error(self, error_message: str):
        self._set_generating_state(False)
        if self._is_streaming:
            self._is_streaming = False
            self.main_window.response_panel.end_stream()

    def _set_generating_state(self, state: bool):
        self._is_generating = state
        self.main_window.action_buttons_panel.set_generating_state(state)
        if not state:
            self._update_navigation_buttons()
            self.main_window.action_buttons_panel.update_text_action_buttons(bool(self.get_input_text().strip()))

    def _handle_stream_chunk(self, chunk: str):
        if not self._is_streaming:
            self._is_streaming = True
            self.main_window.response_panel.start_stream()
        self.main_window.response_panel.append_stream_chunk(chunk)

    def _handle_thinking_chunk(self, chunk: str):
        if not self._is_streaming:
            self._is_streaming = True
            self.main_window.response_panel.start_stream()
        self.main_window.response_panel.append_thinking_chunk(chunk)

    def _handle_stream_complete(self, full_response: str):
        self.main_window.response_panel.end_stream()

    def _handle_navigation(self, direction: str):
        if self._is_generating:
            return self.update_status("Cannot navigate while generating.")

        current_chat_id = self.chat_history_service.get_current_chat_id()
        if current_chat_id and self.chat_history_service.get_current_messages():
            chat_file = Path("chats") / f"{current_chat_id}.json"
            if not chat_file.exists():
                self.chat_history_service.save_current_chat()

        adjacent_id = self.chat_history_service.get_adjacent_chat_id(direction)
        if adjacent_id:
            if self.chat_history_service.load_chat(adjacent_id):
                self.update_status(f"Loaded chat: {adjacent_id}")
            else:
                self.update_status(f"Failed to load chat: {adjacent_id}")
        elif direction == "left":
            self.update_status("No previous chat.")
        else:
            self.handle_new_chat()
        self._update_navigation_buttons()

    def _handle_chat_loaded(self, chat_data: dict):
        self.main_window.response_panel.clear()
        for message in chat_data.get("messages", []):
            role = message.get("role", "")
            content = message.get("content", "")
            filenames = message.get("filenames") or ([message["filename"]] if message.get("filename") else None)

            if role == "user":
                self.append_user_message_signal.emit(content, filenames)
            elif role == "assistant":
                self.main_window.response_panel.append_assistant_message(content)

        self._update_navigation_buttons()
        QTimer.singleShot(0, self.main_window.response_panel.scroll_to_bottom)

    def _update_navigation_buttons(self):
        can_go_left = self.chat_history_service.get_adjacent_chat_id("left") is not None
        can_go_right = self.chat_history_service.get_adjacent_chat_id("right") is not None
        self.main_window.action_buttons_panel.update_navigation_buttons(can_go_left, can_go_right)

    def _update_service_model_button_label(self):
        self.main_window.action_buttons_panel.set_service_model_text(self.selected_service, self.selected_model)

    def _get_active_service(self):
        return self.services.get(self.selected_service, self.services["Gemini"])

    def _confirm_dialog(self, title: str, text: str) -> bool:
        """Show a dark-themed confirmation dialog. Returns True if user confirmed."""
        msg_box = QMessageBox(self.main_window)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setStyleSheet(DARK_MSGBOX_STYLE)
        return msg_box.exec() == QMessageBox.StandardButton.Yes

    def get_input_text(self) -> str:
        return self.main_window.get_input_text()

    def update_status(self, message: str):
        self.main_window.status_signal.emit(message)

    @staticmethod
    def _get_mime_type(filename: str) -> str:
        import mimetypes
        return mimetypes.guess_type(filename)[0] or "application/octet-stream"