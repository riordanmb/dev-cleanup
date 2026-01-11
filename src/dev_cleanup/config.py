"""Configuration management for dev-cleanup."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".dev-cleanup"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "roots": [str(Path.home() / "Projects"), str(Path.home() / "2025-Projects")],
    "older_than_months": 6,
    "cleanable_dirs": ["node_modules", "venv", ".venv", "env"],
}


def load_config() -> dict:
    """Load configuration, merging with defaults.

    Returns:
        Configuration dictionary
    """
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE) as f:
            user_config = json.load(f)
        # Merge with defaults
        config = DEFAULT_CONFIG.copy()
        config.update(user_config)
        return config
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Persist configuration.

    Args:
        config: Configuration dictionary to save
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
