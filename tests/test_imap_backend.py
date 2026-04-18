from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from backends import imap as backend


@pytest.fixture(autouse=True)
def gmail_env(monkeypatch):
    monkeypatch.setattr(backend, "GMAIL_ADDRESS", "you@example.com")
    monkeypatch.setattr(backend, "GMAIL_APP_PASSWORD", "secret")


def _make_imap_mock(uid_to_msgid_and_headers: dict[bytes, tuple[bytes, bytes]]):
    """Build a mock IMAP connection that returns canned UIDs, msg IDs, and headers per query.

    The uid_info bytes are formatted to include both UID and X-GM-MSGID so this helper
    works for both the current code (UID-based parsing) and Task 7's code (X-GM-MSGID parsing).
    """
    mail = MagicMock()
    mail.select.return_value = ("OK", [b"1"])

    def uid_call(command, *args):
        if command == "search":
            return ("OK", [b" ".join(uid_to_msgid_and_headers.keys())])
        if command == "fetch":
            uid_list = args[0]
            requested = uid_list.split(b",")
            response: list = []
            for uid in requested:
                msgid_decimal, headers = uid_to_msgid_and_headers[uid]
                # Include both UID and X-GM-MSGID so parsing works in either code state.
                uid_info = b"NN (UID " + uid + b" X-GM-MSGID " + msgid_decimal + b" BODY[HEADER...] {N}"
                response.append((uid_info, headers))
                response.append(b")")
            return ("OK", response)
        raise AssertionError(f"unexpected uid call: {command} {args}")

    mail.uid.side_effect = uid_call
    return mail


def _patch_imap(monkeypatch, mail):
    @contextmanager
    def fake_imap():
        yield mail
    monkeypatch.setattr(backend, "_imap", fake_imap)


def test_search_emails_accepts_list_returns_sectioned_output(monkeypatch):
    headers_a = b"From: alice@example.com\r\nSubject: Hello\r\nDate: Sat, 18 Apr 2026 10:00:00 +0000\r\n\r\n"
    mail = _make_imap_mock({b"42": (b"1655752825319194624", headers_a)})
    _patch_imap(monkeypatch, mail)

    result = backend.search_emails(["is:unread", "from:bob"], max_results=5)

    assert "=== Query: is:unread ===" in result
    assert "=== Query: from:bob ===" in result
    assert "From: alice@example.com" in result


def test_search_emails_string_input_keeps_unsectioned_output(monkeypatch):
    headers_a = b"From: alice@example.com\r\nSubject: Hello\r\nDate: Sat, 18 Apr 2026 10:00:00 +0000\r\n\r\n"
    mail = _make_imap_mock({b"42": (b"1655752825319194624", headers_a)})
    _patch_imap(monkeypatch, mail)

    result = backend.search_emails("is:unread", max_results=5)

    assert "=== Query:" not in result
    assert "From: alice@example.com" in result


def test_search_results_include_hex_msgid_and_url(monkeypatch):
    """X-GM-MSGID arrives as decimal; output should expose hex + web URL."""
    msgid_hex = "16fa6a6c0d000000"
    headers = b"From: alice@example.com\r\nSubject: Hello\r\nDate: Sat, 18 Apr 2026 10:00:00 +0000\r\n\r\n"
    mail = _make_imap_mock({b"42": (b"1655752825319194624", headers)})
    _patch_imap(monkeypatch, mail)

    result = backend.search_emails("is:unread", max_results=5)

    assert f"[uid:{msgid_hex}]" in result
    assert f"https://mail.google.com/mail/u/you@example.com/#all/{msgid_hex}" in result


def test_read_email_accepts_hex_id_and_includes_url(monkeypatch):
    msgid_hex = "16fa6a6c0d000000"
    msgid_decimal = "1655752825319194624"

    rfc822 = (
        b"From: alice@example.com\r\n"
        b"To: you@example.com\r\n"
        b"Subject: Hello\r\n"
        b"Date: Sat, 18 Apr 2026 10:00:00 +0000\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Body text here.\r\n"
    )

    mail = MagicMock()
    mail.select.return_value = ("OK", [b"1"])
    captured: dict = {}

    def uid_call(command, *args):
        if command == "search":
            captured["search_args"] = (command,) + args
            return ("OK", [b"42"])
        if command == "fetch":
            return ("OK", [(b"42 (RFC822 {N}", rfc822), b")"])
        raise AssertionError(command)

    mail.uid.side_effect = uid_call
    _patch_imap(monkeypatch, mail)

    result = backend.read_email(msgid_hex)

    # Confirm the IMAP search used X-GM-MSGID with the decimal form
    assert captured["search_args"] == ("search", "X-GM-MSGID", msgid_decimal)

    # Output contains the URL header line and the body
    assert f"https://mail.google.com/mail/u/you@example.com/#all/{msgid_hex}" in result
    assert "Body text here." in result
