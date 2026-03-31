import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def gmail_env(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")


@pytest.fixture
def mock_smtp():
    with patch("server.smtplib.SMTP") as mock:
        instance = MagicMock()
        mock.return_value.__enter__.return_value = instance
        yield instance
