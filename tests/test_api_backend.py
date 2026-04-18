import base64
from unittest.mock import MagicMock, patch

import pytest

from backends import api as backend


@pytest.fixture
def fake_service():
    """Patch backends.api.build to return a controllable Gmail service mock."""
    service = MagicMock()
    with patch("backends.api.build", return_value=service):
        yield service


@pytest.fixture(autouse=True)
def fake_credentials():
    """Avoid touching the real token file."""
    with patch("backends.api._load_credentials", return_value=MagicMock()):
        yield


@pytest.fixture(autouse=True)
def cached_account_email(monkeypatch):
    monkeypatch.setattr(backend, "_ACCOUNT_EMAIL", "you@example.com")
    monkeypatch.setattr(backend, "_SERVICE", None)


def test_send_email_calls_users_messages_send_with_base64url_raw(fake_service):
    fake_service.users().messages().send().execute.return_value = {"id": "abc"}

    result = backend.send_email(
        to="alice@example.com",
        subject="Hi",
        body="hello there",
    )

    assert "sent successfully" in result
    sent_call = fake_service.users().messages().send.call_args
    raw = sent_call.kwargs["body"]["raw"]
    decoded = base64.urlsafe_b64decode(raw.encode()).decode()
    assert "To: alice@example.com" in decoded
    assert "Subject: Hi" in decoded
    assert "hello there" in decoded


def test_send_email_includes_attachment(fake_service, tmp_path):
    fake_service.users().messages().send().execute.return_value = {"id": "abc"}

    attachment = tmp_path / "report.txt"
    attachment.write_text("hello")

    result = backend.send_email(
        to="alice@example.com",
        subject="With file",
        body="see attached",
        attachments=[str(attachment)],
    )

    assert "sent successfully" in result
    raw = fake_service.users().messages().send.call_args.kwargs["body"]["raw"]
    decoded = base64.urlsafe_b64decode(raw.encode()).decode()
    assert "report.txt" in decoded


def test_send_email_skips_missing_attachment_with_warning(fake_service):
    fake_service.users().messages().send().execute.return_value = {"id": "abc"}

    result = backend.send_email(
        to="alice@example.com",
        subject="Test",
        body="Body",
        attachments=["/nonexistent/file.pdf"],
    )

    assert "sent successfully" in result
    assert "Warning" in result
    assert "/nonexistent/file.pdf" in result
