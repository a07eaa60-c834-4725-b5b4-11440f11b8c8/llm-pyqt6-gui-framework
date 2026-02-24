"""Configuration Manager for PyQt6 GUI Framework."""
import os
import json

_DEFAULTS = {
    "window_width": 1200,
    "window_height": 800,
    "theme": "dark",
    "current_service": "Gemini",
    "current_model": "Flash",
    "default_system_prompt": "You are a helpful AI assistant."
}

class ConfigManager:
    """Manages GUI configuration values and local gui_config.json persistence."""

    def __init__(self, config_file: str = "gui_config.json"):
        self.config_file = config_file
        self.__dict__.update(_DEFAULTS)
        self._load_config()

    def _load_config(self) -> None:
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                for k in _DEFAULTS:
                    setattr(self, k, config.get(k, getattr(self, k)))
                if "default_service" in config and "current_service" not in config:
                    self.current_service = config["default_service"]
                if "service_models" in config and "current_model" not in config:
                    self.current_model = config.get("service_models", {}).get(self.current_service, self.current_model)
        except Exception:
            pass

    def save(self) -> None:
        try:
            with open(self.config_file, 'w') as f:
                json.dump({k: getattr(self, k) for k in _DEFAULTS}, f, indent=2)
        except Exception:
            pass
