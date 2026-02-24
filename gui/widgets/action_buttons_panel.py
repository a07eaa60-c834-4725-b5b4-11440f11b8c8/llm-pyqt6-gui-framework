# gui/widgets/action_buttons_panel.py
"""
Action Buttons Panel - Contains action buttons for the chat framework GUI.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy, QFileDialog, QVBoxLayout, QGridLayout
from PyQt6.QtCore import pyqtSignal, Qt, QBuffer, QIODevice, QTimer, QEvent
from PyQt6.QtGui import QCursor



class ActionButtonsPanel(QWidget):
    """A panel containing all action buttons for the chat framework."""

    # Signals
    interrupt_signal = pyqtSignal()
    service_model_selected_signal = pyqtSignal(str, str)  # service, model
    select_file_signal = pyqtSignal(str, str)  # base64, filename
    send_signal = pyqtSignal()
    new_chat_signal = pyqtSignal()
    delete_chat_signal = pyqtSignal()
    delete_all_chats_signal = pyqtSignal()
    navigate_left_signal = pyqtSignal()
    navigate_right_signal = pyqtSignal()

    # Service to available models mapping
    SERVICE_MODELS = {
        "Gemini": ["Flash", "Pro"],
        "NVIDIA NIM": ["DeepSeek V3.2", "Kimi K2"]
    }

    SERVICE_MODEL_OPTIONS = [(s, m) for s, models in SERVICE_MODELS.items() for m in models]

    def __init__(self, file_service, parent=None):
        super().__init__(parent)
        self.file_service = file_service
        self.file_service.files_updated.connect(self._update_file_controls_state)
        self.file_service.files_cleared.connect(self._update_file_controls_state)
        
        self._is_generating = False

        # Hover menu state
        self.active_dropdown = None
        self.hide_timer = QTimer()
        self.hide_timer.setInterval(250)
        self.hide_timer.timeout.connect(self._hide_dropdown)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Current selections
        self.current_service = "Gemini"
        self.current_model = "Flash"

        self._create_buttons()

    BLUE = ("#1E88E5", "#2A9BF8", "#1966C2")
    GREEN = ("#4CAF50", "#5CBF60", "#45A049")
    RED = ("#F44336", "#EF5350", "#D32F2F")
    GREY = ("#9E9E9E", "#BDBDBD", "#757575")
    ORANGE = ("#FF6B35", "#FF8C5A", "#E5562A")

    @staticmethod
    def _btn_style(colors, padding="8px"):
        bg, hover, pressed = colors
        return f"""
            QPushButton {{ background-color: {bg}; color: white; font-weight: bold; font-size: 10pt; border: 2px solid {bg}; border-radius: 4px; padding: {padding}; }}
            QPushButton:hover {{ background-color: {hover}; border-color: {hover}; }}
            QPushButton:pressed {{ background-color: {pressed}; border-color: {pressed}; }}
            QPushButton:disabled {{ background-color: #CCCCCC; color: #666666; border-color: #CCCCCC; }}
        """

    def _create_buttons(self):
        def make_btn(text, style, tooltip=""):
            btn = QPushButton(text)
            btn.setStyleSheet(style)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if tooltip: btn.setToolTip(tooltip)
            return btn

        self.service_model_btn = make_btn(f"{self.current_service}:{self.current_model}", self._btn_style(self.BLUE))
        self.service_model_btn.installEventFilter(self)
        self.layout.addWidget(self.service_model_btn, stretch=2)

        chat_mgmt_widget = QWidget()
        chat_mgmt_layout = QGridLayout(chat_mgmt_widget)
        chat_mgmt_layout.setContentsMargins(0, 0, 0, 0)
        chat_mgmt_layout.setSpacing(2)

        self.new_chat_btn = make_btn("🆕", self._btn_style(self.GREEN, "4px"), tooltip="New Chat")
        self.new_chat_btn.clicked.connect(self.new_chat_signal.emit)
        chat_mgmt_layout.addWidget(self.new_chat_btn, 0, 0)

        self.delete_chat_btn = make_btn("🗑️", self._btn_style(self.RED, "4px"), tooltip="Delete Chat")
        self.delete_chat_btn.clicked.connect(self.delete_chat_signal.emit)
        chat_mgmt_layout.addWidget(self.delete_chat_btn, 0, 1)

        self.nav_left_btn = make_btn("◀", "", tooltip="Previous Chat")
        self.nav_left_btn.clicked.connect(self.navigate_left_signal.emit)
        chat_mgmt_layout.addWidget(self.nav_left_btn, 1, 0)

        self.nav_right_btn = make_btn("▶", "", tooltip="Next Chat")
        self.nav_right_btn.clicked.connect(self.navigate_right_signal.emit)
        chat_mgmt_layout.addWidget(self.nav_right_btn, 1, 1)
        
        self.update_navigation_buttons(False, False)

        chat_mgmt_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        chat_mgmt_widget.setMaximumHeight(40)
        for btn in [self.new_chat_btn, self.delete_chat_btn, self.nav_left_btn, self.nav_right_btn]:
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        self.layout.addWidget(chat_mgmt_widget, stretch=1)

        select_file_container = QWidget()
        select_file_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        select_file_container_layout = QHBoxLayout(select_file_container)
        select_file_container_layout.setContentsMargins(0, 0, 0, 0)
        select_file_container_layout.setSpacing(0)
        
        self.select_file_btn = make_btn("Attach", self._btn_style(self.ORANGE))
        self.select_file_btn.setAcceptDrops(True)
        self.select_file_btn.dragEnterEvent = self._upload_drag_enter
        self.select_file_btn.dropEvent = self._upload_drop
        self.select_file_btn.clicked.connect(self._on_select_file_clicked)
        select_file_container_layout.addWidget(self.select_file_btn)
        
        self.clear_files_btn = make_btn("×", self._btn_style(self.RED, "2px 6px"), tooltip="Clear all files")
        self.clear_files_btn.setStyleSheet(self.clear_files_btn.styleSheet() + "QPushButton { min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; font-size: 12pt; }")
        self.clear_files_btn.clicked.connect(self._on_clear_files_clicked)
        self.clear_files_btn.hide()
        self.clear_files_btn.setParent(select_file_container)
        self.clear_files_btn.raise_()
        
        self.select_file_btn.installEventFilter(self)
        self.layout.addWidget(select_file_container, stretch=2)

        self.send_btn = make_btn("Send", self._btn_style(self.GREEN))
        self.send_btn.clicked.connect(self._on_send_btn_clicked)
        self.send_btn.setEnabled(False)
        self.layout.addWidget(self.send_btn, stretch=2)

        # Set size policies
        for btn in [self.service_model_btn, self.select_file_btn, self.send_btn]:
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # Create unified dropdown
        self._create_unified_dropdown()

    def _create_unified_dropdown(self):
        """Create unified dropdown for service:model selection."""
        parent_window = self.window() or None
        dropdown = QWidget(parent_window)
        dropdown.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        dropdown.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        dropdown.setStyleSheet("QWidget { background-color: #2a2a2a; border: 1px solid #555; border-radius: 4px; }")
        layout = QVBoxLayout(dropdown)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        for service, model in self.SERVICE_MODEL_OPTIONS:
            option_btn = QPushButton(f"{service}:{model}")
            option_btn.setStyleSheet("""
                QPushButton { background-color: transparent; color: white; border: none; text-align: left; padding: 6px 12px; font-size: 9pt; }
                QPushButton:hover { background-color: #3d3d3d; }
            """)
            option_btn.clicked.connect(lambda checked, s=service, m=model: self._on_service_model_selected(s, m))
            layout.addWidget(option_btn)

        dropdown.adjustSize()
        dropdown.hide()
        dropdown.installEventFilter(self)
        self.unified_dropdown = dropdown


    def eventFilter(self, obj, event):
        """Handle hover events for dropdown menus and clear button positioning."""
        et = event.type()

        # Handle select_file_btn resize to reposition clear button
        if hasattr(self, 'select_file_btn') and obj == self.select_file_btn and et == QEvent.Type.Resize:
            self._update_clear_button_position()

        # Enter events
        if et == QEvent.Type.Enter:
            if obj == self.service_model_btn:
                self._show_dropdown("unified")
            elif obj == self.unified_dropdown:
                self.hide_timer.stop()

        # Leave events
        elif et == QEvent.Type.Leave:
            if obj in [self.service_model_btn, self.unified_dropdown]:
                self.hide_timer.start()

        return super().eventFilter(obj, event)
    
    def _update_clear_button_position(self):
        """Update clear button position to top-right of select_file_btn."""
        if not self.clear_files_btn.isVisible():
            return
        btn_rect = self.select_file_btn.geometry()
        clear_btn_size = 20
        # Position at top-right with small offset
        x = btn_rect.right() - clear_btn_size - 4
        y = btn_rect.top() + 4
        self.clear_files_btn.setGeometry(x, y, clear_btn_size, clear_btn_size)

    def _show_dropdown(self, dropdown_type):
        if dropdown_type != "unified": return
        if self._is_generating: return
        self.hide_timer.stop()
        if self.active_dropdown and self.active_dropdown != self.unified_dropdown:
            self.active_dropdown.hide()
        if self.active_dropdown == self.unified_dropdown: return

        self.active_dropdown = self.unified_dropdown
        btn_global_pos = self.service_model_btn.mapToGlobal(self.service_model_btn.rect().topLeft())
        self.unified_dropdown.move(btn_global_pos.x(), btn_global_pos.y() - self.unified_dropdown.height() - 2)
        self.unified_dropdown.show()
        self.unified_dropdown.raise_()

    def _hide_dropdown(self):
        if self.active_dropdown:
            self.active_dropdown.hide()
            self.active_dropdown = None
            self.active_button = None

    def _on_service_model_selected(self, service: str, model: str):
        """Handle unified service:model selection."""
        self.current_service = service
        self.current_model = model
        self.service_model_btn.setText(f"{service}:{model}")
        self._update_file_controls_state()
        
        self.service_model_selected_signal.emit(service, model)
        self._hide_dropdown()

    def _update_file_controls_state(self):
        """Update state of file controls based on current service and file selection."""
        # Disable file selection for Nvidia Nim as it doesn't support attachments
        is_nim = self.current_service == "NVIDIA NIM"
        has_files = self.file_service.has_files()
        
        self.select_file_btn.setEnabled(not is_nim and not self._is_generating)
        
        if self._is_generating:
            # During generation, this is the Cancel button, so keep it enabled
            self.send_btn.setEnabled(True)
        elif has_files:
            # Disable Send button if files attached and NVIDIA NIM selected
            self.send_btn.setEnabled(not is_nim)
        
        # Show/hide clear button based on file state
        self.clear_files_btn.setVisible(has_files)
        self.clear_files_btn.setEnabled(not self._is_generating)
        if has_files:
            self._update_clear_button_position()

    def _on_send_btn_clicked(self):
        if self._is_generating:
            self.interrupt_signal.emit()
        else:
            self.send_signal.emit()

    def set_generating_state(self, state: bool):
        """Enable or disable actions based on whether AI is currently generating."""
        self._is_generating = state
        self.new_chat_btn.setEnabled(not state)
        self.delete_chat_btn.setEnabled(not state)
        self.service_model_btn.setEnabled(not state)
        
        if state:
            self._hide_dropdown()
            self.update_navigation_buttons(False, False)
            self.send_btn.setText("Cancel")
            self.send_btn.setStyleSheet(self._btn_style(self.RED))
            grey_style = self._btn_style(self.GREY, "4px")
            self.new_chat_btn.setStyleSheet(grey_style)
            self.delete_chat_btn.setStyleSheet(grey_style)
        else:
            self.send_btn.setText("Send")
            self.send_btn.setStyleSheet(self._btn_style(self.GREEN))
            self.new_chat_btn.setStyleSheet(self._btn_style(self.GREEN, "4px"))
            self.delete_chat_btn.setStyleSheet(self._btn_style(self.RED, "4px"))
            
        self._update_file_controls_state()

    def update_text_action_buttons(self, has_content: bool):
        """
        Update Send button enabled state based on input text content.

        Args:
            has_content: True if input field has non-whitespace text, False otherwise
        """
        if self._is_generating:
            self.send_btn.setEnabled(True)
            return

        # Only update if no files attached - files take precedence
        if not self.file_service.has_files():
            self.send_btn.setEnabled(has_content)

    def _on_select_file_clicked(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select file(s)", "", "All Files (*)")
        for path in paths: self.file_service.load_file_from_path(path)
        if files := self.file_service.get_files():
            self.select_file_signal.emit(files[0][0] or "", "")
    
    def _on_clear_files_clicked(self):
        """Handle clear files button click."""
        self.file_service.clear_files()
        self.select_file_signal.emit("", "")

    def _upload_drag_enter(self, event):
        """Handle drag enter event for select file button."""
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    event.acceptProposedAction()
                    return
        if md.hasImage():
            event.acceptProposedAction()
            return
        event.ignore()

    def _upload_drop(self, event):
        """Handle drop event for upload button - supports multiple files."""
        try:
            md = event.mimeData()
            if md.hasUrls():
                files_loaded = False
                for url in md.urls():
                    if url.isLocalFile():
                        path = url.toLocalFile()
                        if self.file_service.load_file_from_path(path):
                            files_loaded = True
                if files_loaded:
                    # Emit signal with first file's data for backward compatibility
                    files = self.file_service.get_files()
                    if files:
                        b64, _ = files[0]
                        self.select_file_signal.emit(b64 or "", "")
                    event.acceptProposedAction()
                    return
            elif md.hasImage():
                img = md.imageData()
                if img:
                    buf = QBuffer()
                    buf.open(QIODevice.OpenModeFlag.WriteOnly)
                    img.save(buf, "PNG")
                    if self.file_service.load_file_from_data(bytes(buf.data()), "clipboard"):
                        if files := self.file_service.get_files():
                            self.select_file_signal.emit(files[0][0] or "", "")
                        event.acceptProposedAction()
                        return
        except Exception:
            pass
        event.ignore()

    def set_service_model_text(self, service: str, model: str):
        """Set the text of the unified service:model button."""
        self.current_service = service
        self.current_model = model
        self.service_model_btn.setText(f"{service}:{model}")
        self._update_file_controls_state()

    def update_navigation_buttons(self, can_go_left: bool, can_go_right: bool):
        for btn, enabled in [(self.nav_left_btn, can_go_left), (self.nav_right_btn, can_go_right)]:
            btn.setEnabled(enabled)
            btn.setStyleSheet(self._btn_style(self.BLUE if enabled else self.GREY, "4px"))