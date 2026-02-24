# gui/widgets/input_panel.py
"""
Input Panel - Contains input label and text edit.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QSizePolicy, QMainWindow
from PyQt6.QtCore import QEvent, QTimer, Qt, QSize, pyqtSignal


class InputPanel(QWidget):
    """A panel containing the input label and text edit with dynamic height scaling."""

    # Signals
    send_signal = pyqtSignal()
    navigate_left_signal = pyqtSignal()
    navigate_right_signal = pyqtSignal()
    text_content_changed_signal = pyqtSignal(bool)  # True if input has non-whitespace content

    # Constants
    MIN_INPUT_HEIGHT = 40
    WINDOW_DECORATION_BUFFER = 50
    SCREEN_BUFFER = 100
    FALLBACK_SCREEN_HEIGHT = 2000
    RESIZE_DEBOUNCE_MS = 50
    SCROLLBAR_UPDATE_DELAY_MS = 10
    HEIGHT_CHANGE_THRESHOLD = 1  # pixels

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.panel_layout = QVBoxLayout(self)
        self.panel_layout.setContentsMargins(0, 0, 0, 0)
        self.panel_layout.setSpacing(10)

        self.input_text = QTextEdit()
        self.input_text.setAcceptRichText(False)
        self.input_text.setStyleSheet("background-color: #2a2a2a; color: #ffffff; border: 1px solid #333;")
        self.input_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.input_text.setMinimumHeight(self.MIN_INPUT_HEIGHT)
        self.panel_layout.addWidget(self.input_text, stretch=1)

        # Guard flag to prevent recursive updates
        self._updating_height = False
        
        # Timer for debouncing resize events only (not text changes)
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._update_height)
        
        # Update height immediately on text change to prevent scrollbar flash
        self.input_text.textChanged.connect(self._on_text_changed)
        self.input_text.installEventFilter(self)

    def _get_main_window(self):
        """Traverse up the widget hierarchy to find the main window."""
        widget = self
        while widget:
            if isinstance(widget, QMainWindow):
                return widget
            widget = widget.parentWidget()
        return None

    def showEvent(self, event):
        """Install event filter on main window when shown."""
        super().showEvent(event)
        main_window = self._get_main_window()
        if main_window:
            main_window.installEventFilter(self)
        # Ensure correct initial height is set
        self._update_height()

    def _on_text_changed(self):
        """Handle text changes - update height immediately to prevent scrollbar flash."""
        # Update height immediately (will set scrollbar policy correctly)
        self._update_height()

        # Emit signal for text content state (has non-whitespace content)
        current_text = self.get_input_text()
        has_content = len(current_text.strip()) > 0
        self.text_content_changed_signal.emit(has_content)

    def eventFilter(self, obj, event):
        """Handle resize events on main window and key events on input text."""
        if isinstance(obj, QMainWindow) and event.type() == QEvent.Type.Resize:
            # Use a timer to debounce rapid resize events
            if not self._resize_timer.isActive():
                self._resize_timer.start(self.RESIZE_DEBOUNCE_MS)
        elif obj == self.input_text and event.type() == QEvent.Type.KeyPress:
            # Handle Ctrl+Enter shortcut
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.send_signal.emit()
                return True  # Accept the event
            # Handle Ctrl+Left and Ctrl+Right for navigation
            elif event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_Left:
                    self.navigate_left_signal.emit()
                    return True  # Accept the event
                elif event.key() == Qt.Key.Key_Right:
                    self.navigate_right_signal.emit()
                    return True  # Accept the event
        return super().eventFilter(obj, event)
    
    def minimumSizeHint(self):
        m = self.panel_layout.contentsMargins()
        return QSize(super().minimumSizeHint().width(), self.MIN_INPUT_HEIGHT + self.panel_layout.spacing() + m.top() + m.bottom())
    
    def _calculate_max_height_limit(self, main_window, parent_layout):
        """Calculate the maximum allowed height for the input text area."""
        window_height = main_window.height()
        
        # Get screen available geometry as absolute maximum constraint
        screen = main_window.screen()
        max_screen_height = (
            screen.availableGeometry().height() if screen 
            else self.FALLBACK_SCREEN_HEIGHT
        )
        
        # Get sibling constraints
        response_widget = parent_layout.itemAt(0).widget()
        buttons_widget = parent_layout.itemAt(2).widget()
        
        if not response_widget or not buttons_widget:
            return None
        
        resp_min_h = response_widget.minimumHeight()
        btns_h = buttons_widget.sizeHint().height()
        
        # Calculate layout overhead
        margins = parent_layout.contentsMargins()
        spacing = parent_layout.spacing()
        overhead = margins.top() + margins.bottom() + (spacing * 2)
        
        # Account for panel spacing in InputPanel
        panel_spacing = self.panel_layout.spacing()
        panel_overhead = panel_spacing
        
        # Account for window decorations
        central = main_window.centralWidget()
        if central and central.layout():
            central_margins = central.layout().contentsMargins()
            overhead += central_margins.top() + central_margins.bottom()
        
        limit = min(window_height - self.WINDOW_DECORATION_BUFFER, max_screen_height - self.SCREEN_BUFFER)
        return max(self.MIN_INPUT_HEIGHT, limit - resp_min_h - btns_h - overhead - panel_overhead)
    
    def _calculate_content_height(self):
        """Calculate the desired content height based on document size."""
        doc_h = self.input_text.document().size().height()
        input_margins = self.input_text.contentsMargins()
        return int(doc_h + input_margins.top() + input_margins.bottom())
    
    def _update_scrollbar_policy(self, needs_scrollbar, delay_ms=0):
        def set_policy():
            doc_size = self.input_text.document().size().height()
            policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if (doc_size > self.input_text.viewport().height() or needs_scrollbar) else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            self.input_text.setVerticalScrollBarPolicy(policy)
        QTimer.singleShot(delay_ms, set_policy) if delay_ms > 0 else set_policy()

    def _update_height(self):
        """Calculate and apply dynamic height with constraint-based limits."""
        # Prevent recursive updates
        if self._updating_height:
            return
        
        self._updating_height = True
        try:
            # Get main window and parent widget
            main_window = self._get_main_window()
            if not main_window:
                return

            parent = self.parentWidget()
            if not parent:
                return

            # Validate layout structure
            layout = parent.layout()
            if not layout or layout.count() < 3:
                return

            # Calculate maximum allowed height
            max_limit = self._calculate_max_height_limit(main_window, layout)
            if max_limit is None:
                return

            # Calculate desired content height
            content_h = self._calculate_content_height()
            
            # Clamp to limits
            final_height = max(self.MIN_INPUT_HEIGHT, min(content_h, max_limit))
            needs_scrollbar = content_h > max_limit
            
            # Update height if changed
            current_height = self.input_text.height()
            height_changed = abs(current_height - final_height) > self.HEIGHT_CHANGE_THRESHOLD
            
            if height_changed:
                # Temporarily hide scrollbar during height change to prevent flash
                self.input_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.input_text.setFixedHeight(int(final_height))
                # Update scrollbar policy after layout processes
                self._update_scrollbar_policy(needs_scrollbar, self.SCROLLBAR_UPDATE_DELAY_MS)
            else:
                # Height didn't change, but content might have - update scrollbar immediately
                self._update_scrollbar_policy(needs_scrollbar)
        finally:
            self._updating_height = False

    def get_input_text(self) -> str:
        """Get the text from the input text edit."""
        return self.input_text.toPlainText().strip()

    def set_input_text(self, text: str):
        """Set the text in the input text edit."""
        self.input_text.setPlainText(text)