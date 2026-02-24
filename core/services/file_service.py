# core/services/file_service.py
"""
File Service - Handles file loading, processing, and management for API transmission.
"""
import base64
from typing import Tuple, List
from PyQt6.QtCore import pyqtSignal, QObject


class FileService(QObject):
    """
    Service for handling file operations: loading, encoding for API transmission.
    Supports multiple files.
    """
    files_updated = pyqtSignal(list)  # list of filenames
    files_cleared = pyqtSignal()
    status_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.files_b64: List[str] = []
        self.filenames: List[str] = []

    def _add_file(self, b64: str, filename: str):
        """Add an encoded file and emit update signals."""
        self.files_b64.append(b64)
        self.filenames.append(filename)
        self.files_updated.emit(self.filenames.copy())
        count = len(self.filenames)
        self.status_updated.emit("File loaded." if count == 1 else f"File loaded. Total: {count} files.")

    def load_file_from_path(self, path: str) -> bool:
        """Load file from path and encode to base64. Appends to existing files list."""
        try:
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode("utf-8")
            self._add_file(b64, path.split('/')[-1].split('\\')[-1])
            return True
        except Exception as e:
            self.status_updated.emit(f"❌ Failed to load file: {e}")
            return False

    def load_file_from_data(self, data: bytes, source: str = "") -> bool:
        """Load file from raw data and encode to base64. Appends to existing files list."""
        try:
            self._add_file(base64.b64encode(data).decode("utf-8"), source or "clipboard")
            return True
        except Exception as e:
            self.status_updated.emit(f"❌ Error loading file: {e}")
            return False

    def clear_files(self):
        """Clear all files."""
        self.files_b64.clear()
        self.filenames.clear()
        self.files_cleared.emit()
        self.status_updated.emit("Files cleared.")

    def remove_file(self, index: int) -> bool:
        """
        Remove a specific file by index.

        Args:
            index: Index of file to remove

        Returns:
            bool: True if successful, False if index out of range
        """
        if 0 <= index < len(self.files_b64):
            self.files_b64.pop(index)
            removed_filename = self.filenames.pop(index)
            self.files_updated.emit(self.filenames.copy())
            self.status_updated.emit(f"Removed: {removed_filename}")
            return True
        return False

    def get_files(self) -> List[Tuple[str, str]]:
        """
        Get all file data.

        Returns:
            List of tuples (base64, filename)
        """
        return list(zip(self.files_b64, self.filenames))

    def has_files(self) -> bool:
        """Check if any files are currently loaded."""
        return len(self.files_b64) > 0
