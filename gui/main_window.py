# gui/main_window.py
"""
Main Window GUI - Constructs the main application window and its layout.
"""
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QGridLayout
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence
from gui.widgets.action_buttons_panel import ActionButtonsPanel
from gui.widgets.input_panel import InputPanel
from gui.widgets.response_panel import ResponsePanel




# ========== Main Window Class ==========

class MainWindow(QMainWindow):
    # Signals for communication with main logic
    status_signal = pyqtSignal(str)

    def __init__(self, file_service):
        super().__init__()
        self.file_service = file_service
        self.file_service.files_updated.connect(self._on_files_updated)
        self.file_service.status_updated.connect(self.status_signal.emit)
        self.file_service.files_cleared.connect(self._on_files_cleared)
        self.setWindowTitle("PyQt6 Chat Framework")
        self.setWindowIcon(QIcon("assets/icons/app_icon.ico"))
        self.setStyleSheet("""
            QMainWindow, QStatusBar { background-color: #1a1a1a; }
            QLabel { color: #ffffff; font-family: Arial; }
            QPushButton { background-color: #3d3d3d; color: #ffffff; border: 1px solid #333; padding: 8px; font-family: Arial; font-size: 9pt; border-radius: 4px; }
            QPushButton:hover { background-color: #4d4d4d; }
            QPushButton:pressed { background-color: #2d2d2d; }
            QTextEdit { background-color: #1e1e1e; color: #ffffff; border: 1px solid #333; font-family: Consolas; font-size: 9pt; }
            QStatusBar { color: #888888; font-size: 8pt; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QGridLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 5)

        main_panel = QWidget()
        main_panel_layout = QVBoxLayout(main_panel)
        main_panel_layout.setContentsMargins(0, 0, 0, 0)
        main_panel_layout.setSpacing(10)

        # Add main panel to grid
        main_layout.addWidget(main_panel, 0, 0)

        self._build_main_panel(main_panel_layout)

        # --- Custom Footer ---
        # Status label (bottom-left)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 8pt;")
        self.status_signal.connect(self.status_label.setText)
        main_layout.addWidget(self.status_label, 1, 0, Qt.AlignmentFlag.AlignLeft)

        # --- End Custom Footer ---

        self.status_signal.emit("Ready")

        # Set up keyboard shortcuts
        self._setup_shortcuts()


    def _setup_shortcuts(self):
        """Set up global keyboard shortcuts."""
        # Ctrl+F for search
        search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        search_shortcut.activated.connect(self.response_panel.show_search)

        # Ctrl+Left for navigate left
        nav_left_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
        nav_left_shortcut.activated.connect(lambda: self.action_buttons_panel.navigate_left_signal.emit())

        # Ctrl+Right for navigate right
        nav_right_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        nav_right_shortcut.activated.connect(lambda: self.action_buttons_panel.navigate_right_signal.emit())

        # Ctrl+D for delete all chats
        delete_all_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        delete_all_shortcut.activated.connect(lambda: self.action_buttons_panel.delete_all_chats_signal.emit())


    def _build_main_panel(self, layout):
        self.main_panel_layout = layout  # Store reference to main panel layout

        # Response panel
        self.response_panel = ResponsePanel()
        layout.addWidget(self.response_panel)

        # Input panel
        self.input_panel = InputPanel()
        layout.addWidget(self.input_panel)

        # Action buttons panel
        self.action_buttons_panel = ActionButtonsPanel(self.file_service)
        layout.addWidget(self.action_buttons_panel)

        self.input_panel.text_content_changed_signal.connect(self.action_buttons_panel.update_text_action_buttons)

        self.main_panel_layout.setStretchFactor(self.response_panel, 1)
        self.main_panel_layout.setStretchFactor(self.input_panel, 0)
        self.main_panel_layout.setStretchFactor(self.action_buttons_panel, 0)

    def _on_files_cleared(self):
        self.action_buttons_panel.select_file_signal.emit("", "")

    def _on_files_updated(self, filenames):
        """Handle files updated signal - update status bar with file list."""
        if not filenames:
            self.status_signal.emit("No files selected.")
            return
        
        if len(filenames) == 1:
            self.status_signal.emit(f"File ready: {filenames[0]}")
        else:
            # Show first few filenames, then count
            if len(filenames) <= 3:
                files_str = ", ".join(filenames)
                self.status_signal.emit(f"Files ready: {files_str}")
            else:
                files_str = ", ".join(filenames[:3])
                self.status_signal.emit(f"Files ready: {files_str}... ({len(filenames)} total)")

    def keyPressEvent(self, event):
        """Handle keyboard events - Ctrl+V for clipboard paste."""
        modifiers = event.modifiers()

        # Check for Ctrl+V (or Cmd+V on Mac)
        if (modifiers & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_V:
            # Check if clipboard has image data
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()

            if mime_data.hasImage():
                img = clipboard.image()
                if not img.isNull():
                    # Convert QImage to bytes
                    from PyQt6.QtCore import QBuffer, QIODevice
                    buf = QBuffer()
                    buf.open(QIODevice.OpenModeFlag.WriteOnly)
                    img.save(buf, "PNG")
                    self.file_service.load_file_from_data(bytes(buf.data()), "clipboard.png")
                    return

        # Call parent implementation for other key events
        super().keyPressEvent(event)

    def get_input_text(self) -> str:
        """Get the text from the input text edit."""
        return self.input_panel.get_input_text()

    def closeEvent(self, event):
        """Handle window close event to save window size."""
        if getattr(self, 'config_manager', None):
            self.config_manager.window_width = self.width()
            self.config_manager.window_height = self.height()
            self.config_manager.save()
        event.accept()















