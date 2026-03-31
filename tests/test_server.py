import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def gmail_env(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")
    import server
    monkeypatch.setattr(server, "GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setattr(server, "GMAIL_APP_PASSWORD", "secret")


@pytest.fixture
def mock_smtp():
    with patch("server.smtplib.SMTP") as mock:
        instance = MagicMock()
        mock.return_value.__enter__.return_value = instance
        yield instance


def test_send_with_valid_attachment(mock_smtp, tmp_path):
    attachment = tmp_path / "report.txt"
    attachment.write_text("hello")

    import importlib, server
    importlib.reload(server)

    result = server.send_email(
        to="recipient@example.com",
        subject="Test",
        body="Body",
        attachments=[str(attachment)],
    )

    assert "sent successfully" in result
    assert "Warning" not in result
    mock_smtp.sendmail.assert_called_once()
    raw = mock_smtp.sendmail.call_args[0][2]
    assert "report.txt" in raw
