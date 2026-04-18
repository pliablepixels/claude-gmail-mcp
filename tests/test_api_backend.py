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


def _install_batch(service):
    """Wire a synchronous fake batch on the service mock. Invokes each added
    callback with whatever response the .list().execute() mock is configured to return."""
    batch = MagicMock()
    added: list = []

    def _add(request, callback=None, request_id=None):
        added.append((request_id, callback))

    def _execute():
        list_resp = service.users().messages().list().execute.return_value
        for req_id, cb in added:
            cb(req_id, list_resp, None)

    batch.add.side_effect = _add
    batch.execute.side_effect = _execute
    service.new_batch_http_request.return_value = batch
    return batch


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


def test_search_emails_single_query(fake_service):
    fake_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "16fa6a6c0d000000"}]
    }
    fake_service.users().messages().get().execute.return_value = {
        "id": "16fa6a6c0d000000",
        "payload": {
            "headers": [
                {"name": "From", "value": "alice@example.com"},
                {"name": "Subject", "value": "Hello"},
                {"name": "Date", "value": "Sat, 18 Apr 2026 10:00:00 +0000"},
            ]
        },
    }
    _install_batch(fake_service)

    result = backend.search_emails("is:unread", max_results=5)

    assert "[uid:16fa6a6c0d000000]" in result
    assert "From: alice@example.com" in result
    assert "https://mail.google.com/mail/u/you@example.com/#all/16fa6a6c0d000000" in result
    assert "=== Query:" not in result


def test_search_emails_batch_uses_batch_http_request(fake_service):
    fake_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "abc"}]
    }
    fake_service.users().messages().get().execute.return_value = {
        "id": "abc",
        "payload": {
            "headers": [
                {"name": "From", "value": "x@example.com"},
                {"name": "Subject", "value": "S"},
                {"name": "Date", "value": "D"},
            ]
        },
    }
    batch = _install_batch(fake_service)

    result = backend.search_emails(["q1", "q2"], max_results=5)

    assert "=== Query: q1 ===" in result
    assert "=== Query: q2 ===" in result
    assert fake_service.new_batch_http_request.called
    assert batch.execute.called


def test_read_email_returns_url_headers_and_body(fake_service):
    msg_id = "16fa6a6c0d000000"
    fake_service.users().messages().get().execute.return_value = {
        "id": msg_id,
        "payload": {
            "headers": [
                {"name": "From", "value": "alice@example.com"},
                {"name": "To", "value": "you@example.com"},
                {"name": "Subject", "value": "Hello"},
                {"name": "Date", "value": "Sat, 18 Apr 2026 10:00:00 +0000"},
            ],
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(b"Body text here.").decode()},
        },
    }

    result = backend.read_email(msg_id)

    assert f"https://mail.google.com/mail/u/you@example.com/#all/{msg_id}" in result
    assert "From: alice@example.com" in result
    assert "Subject: Hello" in result
    assert "Body text here." in result


def test_read_email_extracts_text_plain_from_multipart(fake_service):
    msg_id = "abc"
    fake_service.users().messages().get().execute.return_value = {
        "id": msg_id,
        "payload": {
            "headers": [
                {"name": "From", "value": "alice@example.com"},
                {"name": "To", "value": "you@example.com"},
                {"name": "Subject", "value": "Multi"},
                {"name": "Date", "value": "Date"},
            ],
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": base64.urlsafe_b64encode(b"plain version").decode()},
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": base64.urlsafe_b64encode(b"<b>html</b>").decode()},
                },
            ],
        },
    }

    result = backend.read_email(msg_id)

    assert "plain version" in result
    assert "<b>html</b>" not in result
