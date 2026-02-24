# gui/widgets/response_panel.py
"""
Response Panel - Displays chat history with Gemini responses and user inputs.
Read-only, highlightable for copying, no size constraints.
"""

from typing import Optional, List
import html
import markdown
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QSizePolicy, QLineEdit, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import QKeyEvent, QTextCursor


class SearchLineEdit(QLineEdit):
    """Custom QLineEdit with keyboard shortcuts for search widget."""

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            # Close the search widget
            self.parent().close_requested.emit()
            event.accept()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Go to next match
            self.parent().next_requested.emit()
            event.accept()
        else:
            # Default behavior for other keys
            super().keyPressEvent(event)


class SearchWidget(QWidget):
    """A search widget for finding text in the response panel."""

    search_requested = pyqtSignal(str)  # search term
    next_requested = pyqtSignal()
    previous_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px;
                font-size: 10pt;
            }
            QPushButton:hover { background-color: #4d4d4d; }
            QPushButton:pressed { background-color: #2d2d2d; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self.search_requested.emit)
        layout.addWidget(self.search_input)

        self.prev_btn = QPushButton("▲")
        self.prev_btn.setFixedSize(24, 24)
        self.prev_btn.clicked.connect(self.previous_requested.emit)
        layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("▼")
        self.next_btn.setFixedSize(24, 24)
        self.next_btn.clicked.connect(self.next_requested.emit)
        layout.addWidget(self.next_btn)

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_btn)

        self.adjustSize()

    def set_match_count(self, current, total):
        """Update button tooltips with match info."""
        if total > 0:
            self.prev_btn.setToolTip(f"Previous match ({current}/{total})")
            self.next_btn.setToolTip(f"Next match ({current}/{total})")
        else:
            self.prev_btn.setToolTip("No matches")
            self.next_btn.setToolTip("No matches")


class ResponsePanel(QWidget):
    """A panel for displaying chat history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setPlainText("")
        self.response_text.setStyleSheet("background-color: #2a2a2a; color: #ffffff; border: 1px solid #333;")
        self.response_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.response_text.setMinimumHeight(40)
        self.layout.addWidget(self.response_text, stretch=1)

        # Search functionality
        self.search_widget = None
        self.search_matches = []
        self.current_match_index = -1
        
        # Streaming state
        self._is_streaming = False
        self._stream_buffer = ""  # Buffer for current streaming response
        self._thinking_buffer = ""  # Buffer for thinking content
        self._stream_has_thinking = False  # Track if we've received thinking tokens
        
        # Performance: Batched streaming updates
        self._pending_text = ""  # Pending text to be flushed
        self._pending_is_thinking = False  # Type of pending text
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._flush_pending_updates)
        self._update_timer.setInterval(50)  # 50ms batch interval
        
        # Performance: Throttled auto-scroll
        self._scroll_timer = QTimer()
        self._scroll_timer.timeout.connect(self._do_scroll)
        self._scroll_timer.setInterval(100)  # 100ms scroll interval
        self._scroll_pending = False
        
        # Track stream start position for re-rendering
        self._stream_start_cursor_pos = 0
        
        # Color constants
        self.THINKING_COLOR = "#4ECDC4"  # Teal for thinking tokens
        self.ASSISTANT_COLOR = "#ffffff"  # White for regular response
        self.USER_COLOR = "#888888"  # Grey for user messages

    def start_stream(self):
        """Prepare panel for streaming (add new message block)."""
        self._is_streaming = True
        self._stream_buffer = ""
        self._thinking_buffer = ""
        self._stream_has_thinking = False
        self._pending_text = ""
        self._pending_is_thinking = False
        # Move cursor to end and record position for later re-rendering
        self.response_text.moveCursor(QTextCursor.MoveOperation.End)
        self._stream_start_cursor_pos = self.response_text.textCursor().position()
        # Start update timer
        self._update_timer.start()
        self._scroll_timer.start()

    def append_stream_chunk(self, text: str):
        """Append regular response chunk in real-time (white color)."""
        if not text:
            return
        self._stream_buffer += text
        # If switching from thinking to response, add visual separator
        if self._stream_has_thinking and self._pending_is_thinking:
            # Flush any pending thinking text first
            self._flush_pending_updates()
            # Add newline separator between thinking and response
            self.response_text.moveCursor(QTextCursor.MoveOperation.End)
            self.response_text.insertHtml('<br>')
        # Queue for batched update
        self._pending_text += text
        self._pending_is_thinking = False
        self._scroll_pending = True

    def append_thinking_chunk(self, text: str):
        """Append thinking chunk in teal color."""
        if not text:
            return
        self._thinking_buffer += text
        self._stream_has_thinking = True
        # Queue for batched update
        self._pending_text += text
        self._pending_is_thinking = True
        self._scroll_pending = True

    def _flush_pending_updates(self):
        """Flush pending text updates to the display (called by timer)."""
        if not self._pending_text:
            return
        color = self.THINKING_COLOR if self._pending_is_thinking else self.ASSISTANT_COLOR
        html_text = f'<span style="color: {color}; white-space: pre-wrap;">{html.escape(self._pending_text).replace(chr(10), "<br>")}</span>'
        self.response_text.moveCursor(QTextCursor.MoveOperation.End)
        self.response_text.insertHtml(html_text)
        self._pending_text = ""

    def _do_scroll(self):
        """Perform throttled auto-scroll (called by timer)."""
        if self._scroll_pending:
            scrollbar = self.response_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            self._scroll_pending = False

    def end_stream(self):
        """Finalize streaming message with proper markdown rendering."""
        if self._is_streaming:
            # Stop timers
            self._update_timer.stop()
            self._scroll_timer.stop()
            # Flush any remaining pending updates
            self._flush_pending_updates()
            
            self._is_streaming = False
            
            # Re-render the streamed content with proper markdown
            self._rerender_stream_with_markdown()
            
            # Add line break after completed message
            self.response_text.moveCursor(QTextCursor.MoveOperation.End)
            self.response_text.insertHtml("<br>")
            
            # Final scroll to bottom
            scrollbar = self.response_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            # Reset buffers
            self._stream_buffer = ""
            self._thinking_buffer = ""
            self._stream_has_thinking = False

    def _insert_md(self, text: str, color: str, br: bool = True):
        if not text.strip(): return
        self.response_text.moveCursor(QTextCursor.MoveOperation.End)
        html = f'<span style="color: {color};">{markdown.markdown(text, extensions=["extra", "codehilite", "nl2br"])}</span>'
        self.response_text.insertHtml(html + ('<br>' if br else ''))

    def _rerender_stream_with_markdown(self):
        """Remove raw streamed text and replace with markdown-rendered version."""
        cursor = self.response_text.textCursor()
        cursor.setPosition(self._stream_start_cursor_pos)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        
        self._insert_md(self._thinking_buffer, self.THINKING_COLOR, br=bool(self._stream_buffer.strip()))
        self._insert_md(self._stream_buffer, self.ASSISTANT_COLOR, br=False)

    def show_search(self):
        """Show the search widget."""
        if self.search_widget is None:
            self.search_widget = SearchWidget(self.window())
            self.search_widget.search_requested.connect(self.perform_search)
            self.search_widget.next_requested.connect(self.next_match)
            self.search_widget.previous_requested.connect(self.previous_match)
            self.search_widget.close_requested.connect(self.hide_search)

        # Position in top-right
        panel_rect = self.geometry()
        widget_size = self.search_widget.sizeHint()
        x = panel_rect.right() - widget_size.width() - 10
        y = panel_rect.top() + 10
        self.search_widget.move(self.mapToGlobal(panel_rect.topLeft()) + QPoint(x, y))
        self.search_widget.show()
        self.search_widget.raise_()
        self.search_widget.activateWindow()
        # Set focus after the widget is fully shown and activated
        QTimer.singleShot(10, lambda: self.search_widget.search_input.setFocus())

    def hide_search(self):
        """Hide the search widget."""
        if self.search_widget:
            self.search_widget.hide()
            self.clear_search_highlights()

    def perform_search(self, term: str):
        """
        Perform case-insensitive search for the given term in the response text.

        Finds all occurrences of the term, stores their positions, and highlights the first match.
        If no matches found, clears any existing highlights.

        Args:
            term: The search term to find
        """
        if not term:
            self.clear_search_highlights()
            return

        # Get plain text for searching
        plain_text = self.response_text.toPlainText()
        self.search_matches = []
        start = 0
        term_lower = term.lower()

        while True:
            pos = plain_text.lower().find(term_lower, start)
            if pos == -1:
                break
            self.search_matches.append((pos, pos + len(term)))
            start = pos + 1

        if self.search_matches:
            self.current_match_index = 0
            self.update_highlights()
            self.scroll_to_match(0)
        else:
            self.clear_search_highlights()

        self.update_search_widget()

    def navigate_match(self, step: int):
        """Navigate through search matches by step (+1 or -1)."""
        if self.search_matches:
            self.current_match_index = (self.current_match_index + step) % len(self.search_matches)
            self.update_highlights()
            self.scroll_to_match(self.current_match_index)
            self.update_search_widget()

    def next_match(self):
        self.navigate_match(1)

    def previous_match(self):
        self.navigate_match(-1)

    def update_highlights(self):
        """
        Update search highlights using QTextEdit extra selections.

        Applies different highlighting: yellow background for current match,
        cyan background for other matches. Clears previous highlights first.
        """
        from PyQt6.QtGui import QTextCharFormat

        self.response_text.setExtraSelections([])
        if not self.search_matches:
            return

        selections = []
        for i, (start, end) in enumerate(self.search_matches):
            cursor = QTextCursor(self.response_text.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor

            format = QTextCharFormat()
            if i == self.current_match_index:
                # Current match - yellow background, black text
                format.setBackground(Qt.GlobalColor.yellow)
                format.setForeground(Qt.GlobalColor.black)
            else:
                # Other matches - light blue background
                format.setBackground(Qt.GlobalColor.cyan)

            selection.format = format
            selections.append(selection)

        self.response_text.setExtraSelections(selections)

    def clear_search_highlights(self):
        self.response_text.setExtraSelections([])
        self.search_matches.clear()
        self.current_match_index = -1
        self.update_search_widget()

    def scroll_to_match(self, index):
        """
        Scroll the text edit to make the specified match visible.

        Args:
            index: Index of the match in self.search_matches to scroll to
        """
        if 0 <= index < len(self.search_matches):
            start, end = self.search_matches[index]
            cursor = self.response_text.textCursor()
            cursor.setPosition(start)
            self.response_text.setTextCursor(cursor)
            self.response_text.ensureCursorVisible()

    def update_search_widget(self):
        """
        Update the search widget with current match count information.

        Displays current match number and total matches in the widget tooltips.
        """
        if self.search_widget:
            if self.search_matches:
                current = self.current_match_index + 1
                total = len(self.search_matches)
            else:
                current = 0
                total = 0
            self.search_widget.set_match_count(current, total)

    def append_user_message(self, text: str, filenames: Optional[List[str]] = None):
        """Append a user message in grey color."""
        display_text = text
        if filenames:
            display_text = f"{text} [{', '.join(filenames)}]"
        html_text = f'<span style="color: #888888;">{html.escape(display_text).replace(chr(10), "<br>")}</span><br>'
        self.response_text.moveCursor(QTextCursor.MoveOperation.End)
        self.response_text.insertHtml(html_text)

    def append_assistant_message(self, text: str):
        import re
        if match := re.search(r'<thinking>\n?(.*?)\n?</thinking>\n?', text, re.DOTALL):
            self._insert_md(match.group(1), self.THINKING_COLOR, br=bool(text.strip()))
            self._insert_md(text[match.end():].lstrip('\n'), self.ASSISTANT_COLOR)
        else:
            self._insert_md(text, self.ASSISTANT_COLOR)

    def scroll_to_bottom(self):
        """Scroll the response text to the bottom."""
        scrollbar = self.response_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self):
        """Clear the response area."""
        self.response_text.clear()