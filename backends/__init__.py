import os
from pathlib import Path

from backends import imap as imap_backend

DEFAULT_TOKEN_PATH = Path.home() / ".config" / "claude-gmail-mcp" / "token.json"


def _token_path() -> Path:
    override = os.environ.get("GMAIL_TOKEN_PATH")
    return Path(override) if override else DEFAULT_TOKEN_PATH


def detect_backend():
    """Return the active backend module, or None if nothing is configured.

    Detection order:
      1. Token file at GMAIL_TOKEN_PATH (or default) → API backend (added in a later task).
      2. GMAIL_ADDRESS + GMAIL_APP_PASSWORD env → IMAP backend.
      3. None.
    """
    if _token_path().is_file():
        return None  # API backend wired in Task 11.
    if os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"):
        return imap_backend
    return None
