# core/services/chat_history_service.py
"""
Chat History Service - Manages chat history persistence, loading, saving, and navigation.
"""
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal


class ChatHistoryService(QObject):
    """
    Service for managing chat history: saving, loading, and navigating between chats.
    """
    chat_loaded = pyqtSignal(dict)  # Emits chat data when a chat is loaded
    chat_saved = pyqtSignal(str)  # Emits chat ID when a chat is saved

    def __init__(self, chats_dir: str = "chats"):
        """
        Initialize ChatHistoryService.

        Args:
            chats_dir: Directory to store chat JSON files
        """
        super().__init__()
        self.chats_dir = Path(chats_dir)
        self.chats_dir.mkdir(exist_ok=True)
        self.current_chat_id: Optional[str] = None
        self.current_messages: List[Dict[str, str]] = []

    def get_chat_files(self) -> List[Tuple[str, str]]:
        """
        Scan chats directory for JSON files and return sorted list of (chat_id, filepath).

        Returns:
            List of tuples (chat_id, filepath) sorted by timestamp (oldest first)
        """
        chat_files = []
        if not self.chats_dir.exists():
            return chat_files

        for file_path in self.chats_dir.glob("*.json"):
            try:
                # Extract timestamp from filename (YYYY-MM-DD_HH-MM-SS.json)
                chat_id = file_path.stem
                # Validate format
                datetime.strptime(chat_id, "%Y-%m-%d_%H-%M-%S")
                chat_files.append((chat_id, str(file_path)))
            except (ValueError, AttributeError):
                # Skip files that don't match the expected format
                continue

        # Sort by chat_id (which is timestamp-based)
        chat_files.sort(key=lambda x: x[0])
        return chat_files

    def create_new_chat(self) -> str:
        """
        Create a new chat session. No file is created until first message is sent.

        Returns:
            str: New chat ID (timestamp-based)
        """
        self.current_chat_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.current_messages = []
        return self.current_chat_id

    def add_message(self, role: str, content: str, filenames: Optional[List[str]] = None):
        """
        Add a message to the current chat.

        Args:
            role: "user" or "assistant"
            content: Message content
            filenames: Optional list of filenames if message includes file uploads
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        if filenames:
            message["filenames"] = filenames
        self.current_messages.append(message)

    def save_current_chat(self) -> Optional[str]:
        """
        Save the current chat to a JSON file.

        Returns:
            str: Chat ID if saved successfully, None otherwise
        """
        if not self.current_chat_id or not self.current_messages:
            return None

        try:
            chat_data = {
                "chat_id": self.current_chat_id,
                "created_at": self.current_messages[0]["timestamp"] if self.current_messages else datetime.now().isoformat(),
                "messages": self.current_messages
            }

            file_path = self.chats_dir / f"{self.current_chat_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)

            self.chat_saved.emit(self.current_chat_id)
            return self.current_chat_id
        except Exception as e:
            print(f"Error saving chat: {e}")
            return None

    def load_chat(self, chat_id: str) -> Optional[Dict]:
        """
        Load a chat from a JSON file.

        Args:
            chat_id: Chat ID (timestamp-based filename without .json)

        Returns:
            Dict with chat data if successful, None otherwise
        """
        try:
            file_path = self.chats_dir / f"{chat_id}.json"
            if not file_path.exists():
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)

            self.current_chat_id = chat_id
            self.current_messages = chat_data.get("messages", [])
            self.chat_loaded.emit(chat_data)
            return chat_data
        except Exception as e:
            print(f"Error loading chat: {e}")
            return None

    def delete_chat(self, chat_id: str) -> bool:
        """
        Delete a chat file.

        Args:
            chat_id: Chat ID to delete

        Returns:
            bool: True if successful
        """
        try:
            file_path = self.chats_dir / f"{chat_id}.json"
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting chat: {e}")
            return False

    def delete_all_chats(self) -> bool:
        """Delete all chat files."""
        results = [self.delete_chat(chat_id) for chat_id, _ in self.get_chat_files()]
        return all(results) if results else True

    def get_current_chat_id(self) -> Optional[str]:
        """Get the current chat ID."""
        return self.current_chat_id

    def get_current_messages(self) -> List[Dict[str, str]]:
        """Get the current messages list."""
        return self.current_messages.copy()

    def clear_current_chat(self):
        """Clear the current chat without saving."""
        self.current_chat_id = None
        self.current_messages = []

    def get_adjacent_chat_id(self, direction: str) -> Optional[str]:
        """Get the adjacent chat ID in the sorted list."""
        chat_files = self.get_chat_files()
        if not chat_files:
            return None

        if not self.current_chat_id:
            return chat_files[0][0] if direction == "left" else chat_files[-1][0]

        try:
            current_index = next(i for i, (cid, _) in enumerate(chat_files) if cid == self.current_chat_id)
        except StopIteration:
            # Not found, treat as newest
            return chat_files[-1][0] if direction == "left" else None

        if direction == "left" and current_index > 0:
            return chat_files[current_index - 1][0]
        elif direction == "right" and current_index < len(chat_files) - 1:
            return chat_files[current_index + 1][0]
        return None

