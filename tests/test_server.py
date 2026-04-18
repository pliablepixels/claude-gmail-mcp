import os
import pytest
from unittest.mock import patch, MagicMock
import server
from backends import imap as backend


@pytest.fixture(autouse=True)
def gmail_env(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")
    monkeypatch.setattr(backend, "GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setattr(backend, "GMAIL_APP_PASSWORD", "secret")
    monkeypatch.setattr(server, "backend", backend)


@pytest.fixture
def mock_smtp():
    with patch("backends.imap.smtplib.SMTP") as mock:
        instance = MagicMock()
        mock.return_value.__enter__.return_value = instance
        yield instance


def test_send_with_valid_attachment(mock_smtp, tmp_path):
    attachment = tmp_path / "report.txt"
    attachment.write_text("hello")

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


def test_missing_attachment_skipped_with_warning(mock_smtp):
    result = server.send_email(
        to="recipient@example.com",
        subject="Test",
        body="Body",
        attachments=["/nonexistent/path/file.pdf"],
    )

    assert "sent successfully" in result
    assert "Warning" in result
    assert "/nonexistent/path/file.pdf" in result
    mock_smtp.sendmail.assert_called_once()


def test_mixed_attachments_sends_valid_skips_missing(mock_smtp, tmp_path):
    good = tmp_path / "good.txt"
    good.write_text("data")

    result = server.send_email(
        to="recipient@example.com",
        subject="Test",
        body="Body",
        attachments=[str(good), "/nonexistent/bad.pdf"],
    )

    assert "sent successfully" in result
    assert "Warning" in result
    assert "bad.pdf" in result
    mock_smtp.sendmail.assert_called_once()
    raw = mock_smtp.sendmail.call_args[0][2]
    assert "good.txt" in raw


def test_no_attachments_no_warning(mock_smtp):
    result = server.send_email(
        to="recipient@example.com",
        subject="Test",
        body="Body",
    )

    assert "sent successfully" in result
    assert "Warning" not in result
