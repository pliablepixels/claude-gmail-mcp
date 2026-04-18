# Gmail API backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Gmail API backend alongside the existing SMTP/IMAP backend, auto-selected at startup based on the presence of an OAuth token. Add list-of-queries support to `search_emails` and Gmail web URLs to all read/search results.

**Architecture:** Refactor the existing SMTP/IMAP code out of `server.py` into `backends/imap.py`. Add a parallel `backends/api.py`. Both expose the same three functions (`send_email`, `search_emails`, `read_email`) with identical signatures. `backends/__init__.py:detect_backend()` picks one at server startup based on token-file existence, falling back to IMAP env vars, and the slimmed-down `server.py` binds MCP tools to the chosen backend module's functions. A shared `links.py` mints Gmail web URLs and converts between Gmail's hex (used by Gmail API + web URL) and decimal (used by IMAP `X-GM-MSGID` extension) message-ID forms.

**Tech Stack:** Python 3.11+, `mcp[cli]`, `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, `pytest` for tests, `uv` for env management, `imaplib`/`smtplib` retained for the IMAP backend.

---

## File Structure

**New files:**
- `links.py` — Gmail web URL + Gmail message-ID hex/decimal converters.
- `auth.py` — `auth` subcommand: runs the OAuth `InstalledAppFlow` and writes the token file.
- `backends/__init__.py` — `detect_backend()` returns the active backend module.
- `backends/imap.py` — SMTP send + IMAP search/read, refactored from current `server.py`.
- `backends/api.py` — Gmail API implementation of the same three functions.
- `tests/test_links.py`
- `tests/test_backend_detection.py`
- `tests/test_imap_backend.py` — covers the new IMAP behaviours (list queries, hex IDs, URLs).
- `tests/test_api_backend.py`

**Modified files:**
- `server.py` — slim layer: detect backend, log it, expose three `@mcp.tool()` wrappers that delegate.
- `pyproject.toml` — add Google deps and the `claude-gmail-mcp-auth` console script.
- `tests/test_server.py` — update mocks to patch `backends.imap.smtplib.SMTP` instead of `server.smtplib.SMTP`.
- `README.md` — add "Using the Gmail API backend (optional)" section.

---

## Task 1: Add Google API Python dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add deps to pyproject.toml**

Replace the `dependencies = ["mcp[cli]"]` line with:

```toml
dependencies = [
    "mcp[cli]",
    "google-api-python-client",
    "google-auth",
    "google-auth-oauthlib",
]
```

- [ ] **Step 2: Sync the environment**

Run: `uv sync`
Expected: succeeds, prints lines about resolving and installing google-* packages, exits 0.

- [ ] **Step 3: Sanity-check imports**

Run: `uv run python -c "from googleapiclient.discovery import build; from google.oauth2.credentials import Credentials; from google_auth_oauthlib.flow import InstalledAppFlow; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add google-api-python-client, google-auth, google-auth-oauthlib"
```

---

## Task 2: Create `links.py` (URL + hex/decimal helpers)

**Files:**
- Create: `tests/test_links.py`
- Create: `links.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_links.py`:

```python
import pytest

import links


def test_gmail_url_uses_email_in_user_slot():
    url = links.gmail_url("16f3a2b4c5d6e7f8", "alice@example.com")
    assert url == "https://mail.google.com/mail/u/alice@example.com/#all/16f3a2b4c5d6e7f8"


def test_gmail_url_handles_plus_alias():
    url = links.gmail_url("abc123", "alice+work@example.com")
    assert url == "https://mail.google.com/mail/u/alice+work@example.com/#all/abc123"


def test_msgid_decimal_to_hex_accepts_int():
    assert links.msgid_decimal_to_hex(1656870898400000000) == "16fa6a6c0d000000"


def test_msgid_decimal_to_hex_accepts_str():
    assert links.msgid_decimal_to_hex("1656870898400000000") == "16fa6a6c0d000000"


def test_msgid_hex_to_decimal_round_trip():
    decimal = "1656870898400000000"
    hex_form = links.msgid_decimal_to_hex(decimal)
    assert links.msgid_hex_to_decimal(hex_form) == decimal


def test_msgid_hex_to_decimal_strips_optional_0x_prefix():
    assert links.msgid_hex_to_decimal("0x16fa6a6c0d000000") == "1656870898400000000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_links.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'links'`.

- [ ] **Step 3: Create `links.py` with the helpers**

Create `links.py`:

```python
def gmail_url(message_id_hex: str, account_email: str) -> str:
    return f"https://mail.google.com/mail/u/{account_email}/#all/{message_id_hex}"


def msgid_decimal_to_hex(msgid: int | str) -> str:
    return format(int(msgid), "x")


def msgid_hex_to_decimal(msgid_hex: str) -> str:
    cleaned = msgid_hex.lower().removeprefix("0x")
    return str(int(cleaned, 16))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_links.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add links.py tests/test_links.py
git commit -m "feat: add links module for Gmail URLs and message ID conversion"
```

---

## Task 3: Move SMTP/IMAP code into `backends/imap.py` (no behaviour change)

This task is a pure move + import-path update. Tool surface and outputs stay identical so existing tests still pass after the patch-target is updated.

**Files:**
- Create: `backends/__init__.py` (empty for now — package marker only)
- Create: `backends/imap.py`
- Modify: `server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Create the `backends` package marker**

Create `backends/__init__.py`:

```python
```

(Empty file — `detect_backend()` is added in Task 4.)

- [ ] **Step 2: Create `backends/imap.py` with the existing implementation**

Create `backends/imap.py` (copied verbatim from `server.py`, minus the `mcp = FastMCP(...)` and `@mcp.tool()` decorators — these stay in `server.py`):

```python
import email
import imaplib
import os
import smtplib
from contextlib import contextmanager
from email import encoders
from email.header import decode_header as _decode_header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

imaplib._MAXLINE = 10_000_000

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    html: bool = False,
    attachments: list[str] | None = None,
) -> str:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return "Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables must be set."

    if isinstance(to, str):
        to = [to]
    if isinstance(cc, str):
        cc = [cc]
    if isinstance(bcc, str):
        bcc = [bcc]

    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject

    if cc:
        msg["Cc"] = ", ".join(cc)

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type))

    skipped = []
    for path in attachments or []:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            skipped.append(f"could not attach '{path}' (file not found or unreadable)")
            continue
        part = MIMEBase("application", "octet-stream")
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=os.path.basename(path),
        )
        msg.attach(part)

    all_recipients = list(to)
    if cc:
        all_recipients.extend(cc)
    if bcc:
        all_recipients.extend(bcc)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, all_recipients, msg.as_string())
        recipient_summary = ", ".join(to)
        result = f"Email sent successfully to {recipient_summary} with subject '{subject}'."
        if skipped:
            result += " Warning: " + "; ".join(skipped) + "."
        return result
    except smtplib.SMTPAuthenticationError:
        return "Error: Authentication failed. Check your GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
    except Exception as e:
        return f"Error sending email: {e}"


def _decode_str(value: str | None) -> str:
    if not value:
        return ""
    parts = _decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


@contextmanager
def _imap():
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        yield mail
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def search_emails(query: str, max_results: int = 10) -> str:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return "Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set."
    try:
        with _imap() as mail:
            mail.select('"[Gmail]/All Mail"', readonly=True)
            _, data = mail.uid("search", "X-GM-RAW", query)
            uids = data[0].split()
            if not uids:
                return "No messages found."
            uids = uids[-max_results:][::-1]
            uid_list = b",".join(uids)
            _, msgs = mail.uid(
                "fetch", uid_list, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])"
            )
        results = []
        for part in msgs:
            if not isinstance(part, tuple):
                continue
            uid_info, raw_headers = part
            uid = uid_info.decode().split()[2]
            msg = email.message_from_bytes(raw_headers)
            results.append(
                f"[uid:{uid}] {_decode_str(msg['Date'])} | "
                f"From: {_decode_str(msg['From'])} | "
                f"Subject: {_decode_str(msg['Subject'])}"
            )
        return "\n".join(results) if results else "No messages found."
    except imaplib.IMAP4.error as e:
        return f"IMAP error: {e}"
    except Exception as e:
        return f"Error: {e}"


def read_email(uid: str) -> str:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return "Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set."
    try:
        with _imap() as mail:
            mail.select('"[Gmail]/All Mail"', readonly=True)
            _, data = mail.uid("fetch", uid, "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        lines = [
            f"From: {_decode_str(msg['From'])}",
            f"To: {_decode_str(msg['To'])}",
            f"Subject: {_decode_str(msg['Subject'])}",
            f"Date: {msg['Date']}",
            "",
        ]
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    charset = part.get_content_charset() or "utf-8"
                    lines.append(part.get_payload(decode=True).decode(charset, errors="replace"))
                    break
        else:
            charset = msg.get_content_charset() or "utf-8"
            lines.append(msg.get_payload(decode=True).decode(charset, errors="replace"))
        return "\n".join(lines)
    except imaplib.IMAP4.error as e:
        return f"IMAP error: {e}"
    except Exception as e:
        return f"Error: {e}"
```

- [ ] **Step 3: Replace `server.py` with thin wrappers**

Overwrite `server.py`:

```python
from mcp.server.fastmcp import FastMCP

from backends import imap as backend

mcp = FastMCP("gmail")


@mcp.tool()
def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    html: bool = False,
    attachments: list[str] | None = None,
) -> str:
    """Send an email via Gmail SMTP.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body content (plain text or HTML).
        cc: CC recipient(s), optional.
        bcc: BCC recipient(s), optional.
        html: If True, send body as HTML instead of plain text.
        attachments: List of local file paths to attach, optional.
            Files that cannot be read are skipped with a warning.
    """
    return backend.send_email(to, subject, body, cc=cc, bcc=bcc, html=html, attachments=attachments)


@mcp.tool()
def search_emails(query: str, max_results: int = 10) -> str:
    """Search Gmail using full Gmail search syntax (from:, subject:, is:unread, etc).
    Returns UID, sender, subject, and date for each match.

    Args:
        query: Gmail search query, e.g. 'is:unread subject:invoice'
        max_results: Max emails to return (default 10)
    """
    return backend.search_emails(query, max_results=max_results)


@mcp.tool()
def read_email(uid: str) -> str:
    """Fetch the full content of an email by its UID (from search_emails results).

    Args:
        uid: Email UID shown in search_emails output
    """
    return backend.read_email(uid)


if __name__ == "__main__":
    mcp.run()
```

(Tools' `query` / `max_results` signatures and the docstring will be updated in Tasks 6–8 once the new behaviour is added.)

- [ ] **Step 4: Update existing test to patch the new SMTP location**

Edit `tests/test_server.py` — change the imports and patch targets:

Replace:
```python
import server
```
with:
```python
import server
from backends import imap as backend
```

Replace:
```python
    monkeypatch.setattr(server, "GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setattr(server, "GMAIL_APP_PASSWORD", "secret")
```
with:
```python
    monkeypatch.setattr(backend, "GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setattr(backend, "GMAIL_APP_PASSWORD", "secret")
```

Replace:
```python
    with patch("server.smtplib.SMTP") as mock:
```
with:
```python
    with patch("backends.imap.smtplib.SMTP") as mock:
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: 4 tests pass (test_links 6 + test_server 4 = 10 total). All test_server tests should still pass — same behaviour, new patch targets.

- [ ] **Step 6: Commit**

```bash
git add backends/ server.py tests/test_server.py
git commit -m "refactor: move SMTP/IMAP code into backends/imap.py"
```

---

## Task 4: Add `detect_backend()` (IMAP-only branch first)

**Files:**
- Create: `tests/test_backend_detection.py`
- Modify: `backends/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_detection.py`:

```python
import pytest

import backends
from backends import imap as imap_backend


def test_detect_returns_imap_when_app_password_env_set(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_ADDRESS", "you@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "missing.json"))
    assert backends.detect_backend() is imap_backend


def test_detect_returns_none_when_nothing_configured(monkeypatch, tmp_path):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "missing.json"))
    assert backends.detect_backend() is None


def test_detect_returns_none_when_only_address_set(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_ADDRESS", "you@example.com")
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "missing.json"))
    assert backends.detect_backend() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backend_detection.py -v`
Expected: FAIL with `AttributeError: module 'backends' has no attribute 'detect_backend'`.

- [ ] **Step 3: Implement `detect_backend()`**

Replace `backends/__init__.py` with:

```python
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
        return None  # API backend wired in Task 12.
    if os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"):
        return imap_backend
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_backend_detection.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backends/__init__.py tests/test_backend_detection.py
git commit -m "feat: add detect_backend() with IMAP and no-backend branches"
```

---

## Task 5: Wire `server.py` to use `detect_backend()`

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Update server.py to dispatch via detect_backend()**

Replace `server.py`:

```python
import sys

from mcp.server.fastmcp import FastMCP

import backends

mcp = FastMCP("gmail")
backend = backends.detect_backend()

if backend is None:
    print(
        "[gmail-mcp] no backend configured: set GMAIL_ADDRESS+GMAIL_APP_PASSWORD, "
        "or run 'uvx claude-gmail-mcp-auth <credentials.json>'",
        file=sys.stderr,
    )
else:
    print(f"[gmail-mcp] backend={backend.__name__.split('.')[-1]}", file=sys.stderr)


_NO_BACKEND_MSG = (
    "No backend configured. Set GMAIL_ADDRESS+GMAIL_APP_PASSWORD, "
    "or run 'uvx claude-gmail-mcp-auth <credentials.json>'."
)


@mcp.tool()
def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    html: bool = False,
    attachments: list[str] | None = None,
) -> str:
    """Send an email via Gmail.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body content (plain text or HTML).
        cc: CC recipient(s), optional.
        bcc: BCC recipient(s), optional.
        html: If True, send body as HTML instead of plain text.
        attachments: List of local file paths to attach, optional.
            Files that cannot be read are skipped with a warning.
    """
    if backend is None:
        return _NO_BACKEND_MSG
    return backend.send_email(to, subject, body, cc=cc, bcc=bcc, html=html, attachments=attachments)


@mcp.tool()
def search_emails(query: str, max_results: int = 10) -> str:
    """Search Gmail using full Gmail search syntax (from:, subject:, is:unread, etc).
    Returns UID, sender, subject, and date for each match.

    Args:
        query: Gmail search query, e.g. 'is:unread subject:invoice'
        max_results: Max emails to return (default 10)
    """
    if backend is None:
        return _NO_BACKEND_MSG
    return backend.search_emails(query, max_results=max_results)


@mcp.tool()
def read_email(uid: str) -> str:
    """Fetch the full content of an email by its UID (from search_emails results).

    Args:
        uid: Email UID shown in search_emails output
    """
    if backend is None:
        return _NO_BACKEND_MSG
    return backend.read_email(uid)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest -v`
Expected: all previously passing tests still pass (test_server.py path goes via the new dispatch but lands in `backends.imap.send_email` as before).

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "refactor: server.py dispatches to detected backend"
```

---

## Task 6: IMAP `search_emails` — accept list of queries

Add list-of-queries support to the IMAP backend. Keep the single-query string signature working.

**Files:**
- Create: `tests/test_imap_backend.py`
- Modify: `backends/imap.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_imap_backend.py`:

```python
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
    mail = _make_imap_mock({b"42": (b"1656870898400000000", headers_a)})
    _patch_imap(monkeypatch, mail)

    result = backend.search_emails(["is:unread", "from:bob"], max_results=5)

    assert "=== Query: is:unread ===" in result
    assert "=== Query: from:bob ===" in result
    assert "From: alice@example.com" in result


def test_search_emails_string_input_keeps_unsectioned_output(monkeypatch):
    headers_a = b"From: alice@example.com\r\nSubject: Hello\r\nDate: Sat, 18 Apr 2026 10:00:00 +0000\r\n\r\n"
    mail = _make_imap_mock({b"42": (b"1656870898400000000", headers_a)})
    _patch_imap(monkeypatch, mail)

    result = backend.search_emails("is:unread", max_results=5)

    assert "=== Query:" not in result
    assert "From: alice@example.com" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_imap_backend.py -v`
Expected: FAIL — current `search_emails` treats list inputs as a single query string and won't produce the `=== Query:` headers.

- [ ] **Step 3: Update `search_emails` to accept list**

In `backends/imap.py`, replace the existing `search_emails` function with:

```python
def search_emails(queries: str | list[str], max_results: int = 10) -> str:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return "Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set."

    is_batch = isinstance(queries, list)
    query_list = queries if is_batch else [queries]

    try:
        sections = []
        with _imap() as mail:
            mail.select('"[Gmail]/All Mail"', readonly=True)
            for query in query_list:
                section = _search_one(mail, query, max_results)
                if is_batch:
                    sections.append(f"=== Query: {query} ===\n{section}")
                else:
                    sections.append(section)
        return "\n\n".join(sections)
    except imaplib.IMAP4.error as e:
        return f"IMAP error: {e}"
    except Exception as e:
        return f"Error: {e}"


def _search_one(mail, query: str, max_results: int) -> str:
    _, data = mail.uid("search", "X-GM-RAW", query)
    uids = data[0].split()
    if not uids:
        return "No messages found."
    uids = uids[-max_results:][::-1]
    uid_list = b",".join(uids)
    _, msgs = mail.uid(
        "fetch", uid_list, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])"
    )
    results = []
    for part in msgs:
        if not isinstance(part, tuple):
            continue
        uid_info, raw_headers = part
        uid = uid_info.decode().split()[2]
        msg = email.message_from_bytes(raw_headers)
        results.append(
            f"[uid:{uid}] {_decode_str(msg['Date'])} | "
            f"From: {_decode_str(msg['From'])} | "
            f"Subject: {_decode_str(msg['Subject'])}"
        )
    return "\n".join(results) if results else "No messages found."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_imap_backend.py -v`
Expected: 2 passed.

Run full suite: `uv run pytest -v`
Expected: all green.

- [ ] **Step 5: Update `server.py` tool signature and docstring**

In `server.py`, replace the `search_emails` tool definition with:

```python
@mcp.tool()
def search_emails(queries: str | list[str], max_results: int = 10) -> str:
    """Search Gmail using full Gmail search syntax (from:, subject:, is:unread, etc).

    Pass a single query string for a flat list of results, or a list of queries
    to run several searches in one call (output is sectioned by query, and
    max_results applies per query).

    Returns UID, sender, subject, date, and a Gmail web URL for each match.

    Args:
        queries: Single query string or list of query strings.
        max_results: Max emails to return per query (default 10).
    """
    if backend is None:
        return _NO_BACKEND_MSG
    return backend.search_emails(queries, max_results=max_results)
```

- [ ] **Step 6: Commit**

```bash
git add backends/imap.py server.py tests/test_imap_backend.py
git commit -m "feat: search_emails accepts list of queries (IMAP backend)"
```

---

## Task 7: IMAP — return Gmail message IDs (hex) and web URLs

Switch the IMAP backend's search/read to use Gmail message IDs (the same hex value Gmail API and the web UI use), and append a Gmail web URL to each search hit and to the top of `read_email` output.

**Files:**
- Modify: `tests/test_imap_backend.py`
- Modify: `backends/imap.py`

- [ ] **Step 1: Add failing tests for hex IDs and URLs**

Append to `tests/test_imap_backend.py`:

```python
def test_search_results_include_hex_msgid_and_url(monkeypatch):
    """X-GM-MSGID arrives as decimal; output should expose hex + web URL."""
    msgid_hex = "16fa6a6c0d000000"
    headers = b"From: alice@example.com\r\nSubject: Hello\r\nDate: Sat, 18 Apr 2026 10:00:00 +0000\r\n\r\n"
    mail = _make_imap_mock({b"42": (b"1656870898400000000", headers)})
    _patch_imap(monkeypatch, mail)

    result = backend.search_emails("is:unread", max_results=5)

    assert f"[uid:{msgid_hex}]" in result
    assert f"https://mail.google.com/mail/u/you@example.com/#all/{msgid_hex}" in result


def test_read_email_accepts_hex_id_and_includes_url(monkeypatch):
    msgid_hex = "16fa6a6c0d000000"
    msgid_decimal = "1656870898400000000"

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_imap_backend.py -v`
Expected: the two new tests fail (no hex/URL in current output; `read_email` uses raw UID fetch).

- [ ] **Step 3: Update `_search_one` to fetch X-GM-MSGID and emit hex + URL**

In `backends/imap.py`, add at the top:

```python
import links
```

Replace `_search_one` with:

```python
def _search_one(mail, query: str, max_results: int) -> str:
    _, data = mail.uid("search", "X-GM-RAW", query)
    uids = data[0].split()
    if not uids:
        return "No messages found."
    uids = uids[-max_results:][::-1]
    uid_list = b",".join(uids)
    _, msgs = mail.uid(
        "fetch",
        uid_list,
        "(X-GM-MSGID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])",
    )
    results = []
    for part in msgs:
        if not isinstance(part, tuple):
            continue
        uid_info, raw_headers = part
        # uid_info looks like:
        #   b"42 (X-GM-MSGID 1656870898400000000 BODY[HEADER...] {N}"
        text = uid_info.decode()
        msgid_decimal = text.split("X-GM-MSGID")[1].split()[0]
        msgid_hex = links.msgid_decimal_to_hex(msgid_decimal)
        msg = email.message_from_bytes(raw_headers)
        url = links.gmail_url(msgid_hex, GMAIL_ADDRESS)
        results.append(
            f"[uid:{msgid_hex}] {_decode_str(msg['Date'])} | "
            f"From: {_decode_str(msg['From'])} | "
            f"Subject: {_decode_str(msg['Subject'])}\n"
            f"  → {url}"
        )
    return "\n".join(results) if results else "No messages found."
```

- [ ] **Step 4: Replace `read_email` to accept hex IDs and include URL**

Replace the existing `read_email` in `backends/imap.py` with:

```python
def read_email(uid: str) -> str:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return "Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set."
    msgid_hex = uid
    try:
        msgid_decimal = links.msgid_hex_to_decimal(msgid_hex)
    except ValueError:
        return f"Error: invalid Gmail message ID '{uid}' (expected hex)."

    try:
        with _imap() as mail:
            mail.select('"[Gmail]/All Mail"', readonly=True)
            _, search_data = mail.uid("search", "X-GM-MSGID", msgid_decimal)
            imap_uids = search_data[0].split()
            if not imap_uids:
                return f"No message found for id {msgid_hex}."
            _, data = mail.uid("fetch", imap_uids[0], "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        url = links.gmail_url(msgid_hex, GMAIL_ADDRESS)
        lines = [
            url,
            f"From: {_decode_str(msg['From'])}",
            f"To: {_decode_str(msg['To'])}",
            f"Subject: {_decode_str(msg['Subject'])}",
            f"Date: {msg['Date']}",
            "",
        ]
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    charset = part.get_content_charset() or "utf-8"
                    lines.append(part.get_payload(decode=True).decode(charset, errors="replace"))
                    break
        else:
            charset = msg.get_content_charset() or "utf-8"
            lines.append(msg.get_payload(decode=True).decode(charset, errors="replace"))
        return "\n".join(lines)
    except imaplib.IMAP4.error as e:
        return f"IMAP error: {e}"
    except Exception as e:
        return f"Error: {e}"
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: all green (existing send tests + new IMAP tests + links + backend detection).

- [ ] **Step 6: Commit**

```bash
git add backends/imap.py tests/test_imap_backend.py
git commit -m "feat: IMAP backend uses Gmail message IDs (hex) and emits web URLs"
```

---

## Task 8: API backend — `send_email`

**Files:**
- Create: `tests/test_api_backend.py`
- Create: `backends/api.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_backend.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_backend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backends.api'`.

- [ ] **Step 3: Create `backends/api.py` with send_email**

Create `backends/api.py`:

```python
import base64
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import links

DEFAULT_TOKEN_PATH = Path.home() / ".config" / "claude-gmail-mcp" / "token.json"

_ACCOUNT_EMAIL: str | None = None
_SERVICE = None


def _token_path() -> Path:
    override = os.environ.get("GMAIL_TOKEN_PATH")
    return Path(override) if override else DEFAULT_TOKEN_PATH


def _load_credentials() -> Credentials:
    return Credentials.from_authorized_user_file(str(_token_path()))


def _service():
    global _SERVICE
    if _SERVICE is None:
        creds = _load_credentials()
        _SERVICE = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return _SERVICE


def _account_email() -> str:
    global _ACCOUNT_EMAIL
    if _ACCOUNT_EMAIL is None:
        profile = _service().users().getProfile(userId="me").execute()
        _ACCOUNT_EMAIL = profile["emailAddress"]
    return _ACCOUNT_EMAIL


_AUTH_RETRY_MSG = (
    "Auth failed — re-run 'uvx claude-gmail-mcp-auth <credentials.json>'."
)


def _format_http_error(e: HttpError) -> str:
    status = getattr(e.resp, "status", None)
    if status in (401, 403):
        return _AUTH_RETRY_MSG
    if status == 429:
        return "Gmail API rate limit hit, try again shortly."
    return f"Gmail API error ({status}): {e}"


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    html: bool = False,
    attachments: list[str] | None = None,
) -> str:
    if isinstance(to, str):
        to = [to]
    if isinstance(cc, str):
        cc = [cc]
    if isinstance(bcc, str):
        bcc = [bcc]

    msg = MIMEMultipart()
    msg["From"] = _account_email()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type))

    skipped = []
    for path in attachments or []:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            skipped.append(f"could not attach '{path}' (file not found or unreadable)")
            continue
        part = MIMEBase("application", "octet-stream")
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=os.path.basename(path),
        )
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        _service().users().messages().send(userId="me", body={"raw": raw}).execute()
    except RefreshError:
        return _AUTH_RETRY_MSG
    except HttpError as e:
        return _format_http_error(e)

    recipient_summary = ", ".join(to)
    result = f"Email sent successfully to {recipient_summary} with subject '{subject}'."
    if skipped:
        result += " Warning: " + "; ".join(skipped) + "."
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_backend.py -v`
Expected: 3 passed.

Run full suite: `uv run pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backends/api.py tests/test_api_backend.py
git commit -m "feat: API backend send_email"
```

---

## Task 9: API backend — `search_emails` (single query, then batch)

**Files:**
- Modify: `tests/test_api_backend.py`
- Modify: `backends/api.py`

- [ ] **Step 1: Write the failing test for single-query search**

Append to `tests/test_api_backend.py`:

```python
def test_search_emails_single_query(fake_service):
    # users.messages.list returns ids
    fake_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "16fa6a6c0d000000"}]
    }
    # users.messages.get returns metadata for that id
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

    result = backend.search_emails("is:unread", max_results=5)

    assert "[uid:16fa6a6c0d000000]" in result
    assert "From: alice@example.com" in result
    assert "https://mail.google.com/mail/u/you@example.com/#all/16fa6a6c0d000000" in result
    assert "=== Query:" not in result  # single string input → no header
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api_backend.py::test_search_emails_single_query -v`
Expected: FAIL with `AttributeError: module 'backends.api' has no attribute 'search_emails'`.

- [ ] **Step 3: Implement single-query `search_emails`**

Append to `backends/api.py`:

```python
def search_emails(queries: str | list[str], max_results: int = 10) -> str:
    is_batch = isinstance(queries, list)
    query_list = queries if is_batch else [queries]

    try:
        per_query_results = _run_searches(query_list, max_results)
    except RefreshError:
        return _AUTH_RETRY_MSG
    except HttpError as e:
        return _format_http_error(e)

    if is_batch:
        sections = [
            f"=== Query: {q} ===\n{per_query_results[q]}" for q in query_list
        ]
        return "\n\n".join(sections)
    return per_query_results[query_list[0]]


def _run_searches(query_list: list[str], max_results: int) -> dict[str, str]:
    results: dict[str, list[str]] = {q: [] for q in query_list}
    ids_per_query: dict[str, list[str]] = {}

    service = _service()

    for query in query_list:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        ids_per_query[query] = [m["id"] for m in resp.get("messages", [])]

    for query, ids in ids_per_query.items():
        for msg_id in ids:
            msg = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            url = links.gmail_url(msg_id, _account_email())
            results[query].append(
                f"[uid:{msg_id}] {headers.get('Date', '')} | "
                f"From: {headers.get('From', '')} | "
                f"Subject: {headers.get('Subject', '')}\n"
                f"  → {url}"
            )

    return {q: "\n".join(lines) if lines else "No messages found." for q, lines in results.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_backend.py -v`
Expected: all API tests pass (4 total now).

- [ ] **Step 5: Add a failing test for batch search using BatchHttpRequest**

Append to `tests/test_api_backend.py`:

```python
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

    with patch("backends.api.BatchHttpRequest") as batch_cls:
        # Capture added requests; "execute" callback must be invoked with results.
        batch_instance = MagicMock()
        added_callbacks: list = []

        def add(request, callback=None, request_id=None):
            added_callbacks.append((request_id, callback))

        batch_instance.add.side_effect = add

        def execute_batch():
            for req_id, cb in added_callbacks:
                cb(req_id, {"messages": [{"id": "abc"}]}, None)

        batch_instance.execute.side_effect = execute_batch
        batch_cls.return_value = batch_instance

        result = backend.search_emails(["q1", "q2"], max_results=5)

    assert "=== Query: q1 ===" in result
    assert "=== Query: q2 ===" in result
    # BatchHttpRequest used once for the list calls
    assert batch_cls.called
    assert batch_instance.execute.called
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_api_backend.py::test_search_emails_batch_uses_batch_http_request -v`
Expected: FAIL — current `_run_searches` calls `list(...).execute()` serially, doesn't touch `BatchHttpRequest`.

- [ ] **Step 7: Refactor `_run_searches` to use `BatchHttpRequest` for the list step**

In `backends/api.py`:

Add to imports:
```python
from googleapiclient.http import BatchHttpRequest
```

Replace `_run_searches` with:

```python
def _run_searches(query_list: list[str], max_results: int) -> dict[str, str]:
    results: dict[str, list[str]] = {q: [] for q in query_list}
    ids_per_query: dict[str, list[str]] = {q: [] for q in query_list}

    service = _service()

    def _make_callback(query: str):
        def _cb(request_id, response, exception):
            if exception is not None:
                raise exception
            ids_per_query[query] = [m["id"] for m in response.get("messages", [])]
        return _cb

    batch = BatchHttpRequest(callback=None)
    for i, query in enumerate(query_list):
        req = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        )
        batch.add(req, callback=_make_callback(query), request_id=str(i))
    batch.execute()

    for query, ids in ids_per_query.items():
        for msg_id in ids:
            msg = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            url = links.gmail_url(msg_id, _account_email())
            results[query].append(
                f"[uid:{msg_id}] {headers.get('Date', '')} | "
                f"From: {headers.get('From', '')} | "
                f"Subject: {headers.get('Subject', '')}\n"
                f"  → {url}"
            )

    return {q: "\n".join(lines) if lines else "No messages found." for q, lines in results.items()}
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest -v`
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add backends/api.py tests/test_api_backend.py
git commit -m "feat: API backend search_emails with batch HTTP for list step"
```

---

## Task 10: API backend — `read_email`

**Files:**
- Modify: `tests/test_api_backend.py`
- Modify: `backends/api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api_backend.py`:

```python
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
            "body": {
                "data": __import__("base64").urlsafe_b64encode(b"Body text here.").decode()
            },
        },
    }

    result = backend.read_email(msg_id)

    assert f"https://mail.google.com/mail/u/you@example.com/#all/{msg_id}" in result
    assert "From: alice@example.com" in result
    assert "Subject: Hello" in result
    assert "Body text here." in result


def test_read_email_extracts_text_plain_from_multipart(fake_service):
    import base64 as b64
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
                    "body": {"data": b64.urlsafe_b64encode(b"plain version").decode()},
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": b64.urlsafe_b64encode(b"<b>html</b>").decode()},
                },
            ],
        },
    }

    result = backend.read_email(msg_id)

    assert "plain version" in result
    assert "<b>html</b>" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_backend.py -v`
Expected: FAIL with `AttributeError: module 'backends.api' has no attribute 'read_email'`.

- [ ] **Step 3: Implement `read_email`**

Append to `backends/api.py`:

```python
def read_email(uid: str) -> str:
    msgid_hex = uid
    try:
        msg = (
            _service()
            .users()
            .messages()
            .get(userId="me", id=msgid_hex, format="full")
            .execute()
        )
    except RefreshError:
        return _AUTH_RETRY_MSG
    except HttpError as e:
        return _format_http_error(e)

    payload = msg["payload"]
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    url = links.gmail_url(msgid_hex, _account_email())
    body_text = _extract_text_plain(payload)

    lines = [
        url,
        f"From: {headers.get('From', '')}",
        f"To: {headers.get('To', '')}",
        f"Subject: {headers.get('Subject', '')}",
        f"Date: {headers.get('Date', '')}",
        "",
        body_text,
    ]
    return "\n".join(lines)


def _extract_text_plain(payload: dict) -> str:
    """Walk a Gmail payload tree and return the first text/plain body, decoded."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")

    for part in payload.get("parts", []) or []:
        text = _extract_text_plain(part)
        if text:
            return text
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_backend.py -v`
Expected: all API tests pass.

Run full suite: `uv run pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backends/api.py tests/test_api_backend.py
git commit -m "feat: API backend read_email"
```

---

## Task 11: Wire API backend into `detect_backend()`

**Files:**
- Modify: `tests/test_backend_detection.py`
- Modify: `backends/__init__.py`

- [ ] **Step 1: Add failing test for API detection**

Append to `tests/test_backend_detection.py`:

```python
def test_detect_returns_api_when_token_file_exists(monkeypatch, tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(
        '{"refresh_token":"x","client_id":"y","client_secret":"z","token_uri":"https://example/token","scopes":["scope"]}'
    )
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_file))

    from backends import api as api_backend
    assert backends.detect_backend() is api_backend


def test_detect_prefers_api_over_imap_when_both_present(monkeypatch, tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(
        '{"refresh_token":"x","client_id":"y","client_secret":"z","token_uri":"https://example/token","scopes":["scope"]}'
    )
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_file))
    monkeypatch.setenv("GMAIL_ADDRESS", "you@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

    from backends import api as api_backend
    assert backends.detect_backend() is api_backend
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_backend_detection.py -v`
Expected: the two new tests FAIL — `detect_backend()` currently returns `None` when the token file exists.

- [ ] **Step 3: Update `detect_backend()` to return the API backend module**

In `backends/__init__.py`, replace `detect_backend` with:

```python
def detect_backend():
    """Return the active backend module, or None if nothing is configured.

    Detection order:
      1. Token file at GMAIL_TOKEN_PATH (or default) → API backend.
      2. GMAIL_ADDRESS + GMAIL_APP_PASSWORD env → IMAP backend.
      3. None.
    """
    if _token_path().is_file():
        from backends import api as api_backend
        return api_backend
    if os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"):
        return imap_backend
    return None
```

(Lazy-import keeps the IMAP-only install from failing if Google deps were ever skipped.)

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backends/__init__.py tests/test_backend_detection.py
git commit -m "feat: detect_backend() prefers Gmail API when token file present"
```

---

## Task 12: `auth` subcommand and console script

The OAuth flow itself is interactive (browser). Not unit-tested — covered by manual smoke test in the README.

**Files:**
- Create: `auth.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create `auth.py`**

Create `auth.py`:

```python
import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

DEFAULT_TOKEN_PATH = Path.home() / ".config" / "claude-gmail-mcp" / "token.json"


def _token_path() -> Path:
    override = os.environ.get("GMAIL_TOKEN_PATH")
    return Path(override) if override else DEFAULT_TOKEN_PATH


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(
            "Usage: claude-gmail-mcp-auth <path/to/credentials.json>\n"
            "\n"
            "Runs a one-time OAuth browser flow and writes a refresh token to\n"
            f"  {DEFAULT_TOKEN_PATH}\n"
            "(or to $GMAIL_TOKEN_PATH if set).",
            file=sys.stderr,
        )
        return 2

    credentials_path = Path(argv[0])
    if not credentials_path.is_file():
        print(f"Error: credentials file not found: {credentials_path}", file=sys.stderr)
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    out = _token_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(creds.to_json())
    out.chmod(0o600)

    print(f"Token written to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add the console script in pyproject.toml**

Edit `pyproject.toml`. Replace:

```toml
[project.scripts]
claude-gmail-mcp = "server:mcp.run"
```

with:

```toml
[project.scripts]
claude-gmail-mcp = "server:mcp.run"
claude-gmail-mcp-auth = "auth:main"
```

- [ ] **Step 3: Re-sync the environment so the script is registered**

Run: `uv sync`
Expected: succeeds.

- [ ] **Step 4: Smoke-test the help output**

Run: `uv run claude-gmail-mcp-auth`
Expected: prints the "Usage: claude-gmail-mcp-auth <path/to/credentials.json>" message to stderr and exits 2.

Run: `uv run claude-gmail-mcp-auth /tmp/does-not-exist.json`
Expected: prints `Error: credentials file not found: /tmp/does-not-exist.json` and exits 1.

(The actual OAuth browser flow can only be tested with real credentials — that's the README smoke test in Task 13.)

- [ ] **Step 5: Commit**

```bash
git add auth.py pyproject.toml uv.lock
git commit -m "feat: add claude-gmail-mcp-auth subcommand for OAuth setup"
```

---

## Task 13: README — document the API backend path

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the new section**

In `README.md`, insert this section between the existing `## Verify` section and the existing `## Usage` section:

```markdown
## Using the Gmail API backend (optional)

Instead of an app password, you can use an OAuth token and the Gmail API. With this backend you get:

- No app password required (OAuth-based auth).
- Batch search: pass a list of queries to `search_emails` and they run in one HTTP roundtrip.
- A direct Gmail web URL is included with every search/read result.

### One-time setup

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project, enable the Gmail API, and create an OAuth client of type **Desktop app**. Download the credentials JSON.
2. Run the auth helper, pointing at the downloaded file:

   ```sh
   uvx --from claude-gmail-mcp claude-gmail-mcp-auth /path/to/credentials.json
   ```

   This opens your browser, you grant access, and a refresh token is saved to `~/.config/claude-gmail-mcp/token.json`.
3. Add the MCP server (no env vars needed if the default token path is used):

   ```sh
   claude mcp add gmail --scope user -- uvx claude-gmail-mcp
   ```

The server picks the API backend automatically when the token file exists. Delete the token file (or unset `GMAIL_TOKEN_PATH`) to fall back to the SMTP/IMAP path.

### Batch search example

> Search Gmail for "is:unread from:alice" and "is:unread from:bob" — show me both lists side by side.

Claude will pass both queries in a single tool call, and the response will be sectioned per query.
```

- [ ] **Step 2: Update the existing Usage section to mention list-of-queries**

In the existing `## Usage` section, find the line that lists `search_emails` parameters (or add it if absent) and ensure it mentions:

> `search_emails` accepts either a single query string or a list of query strings. With a list, results are sectioned per query and `max_results` applies per query.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document Gmail API backend setup and batch search"
```

---

## Task 14: Final smoke test against real Gmail

Manual end-to-end check, no code changes.

- [ ] **Step 1: Verify IMAP backend still works**

With `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` set and no token file:

```sh
GMAIL_TOKEN_PATH=/tmp/no-such-file.json uv run claude-gmail-mcp
```

Confirm stderr shows `[gmail-mcp] backend=imap`. Send a test email to yourself via your Claude Code MCP configuration and confirm receipt.

- [ ] **Step 2: Run the OAuth flow and verify API backend takes over**

```sh
uv run claude-gmail-mcp-auth /path/to/your/credentials.json
```

Browser opens, grant access, token written to `~/.config/claude-gmail-mcp/token.json`.

```sh
uv run claude-gmail-mcp
```

Confirm stderr shows `[gmail-mcp] backend=api`. Through Claude Code:
- Send an email — should arrive.
- Search with a list of two queries — output should be sectioned with `=== Query: ... ===` headers.
- Click a Gmail web URL from the output — should open the right account and message.
- Pass a hex `uid` from `search_emails` to `read_email` — should return body text and the URL header.

If anything fails, fix it before committing.

- [ ] **Step 3: No commit (verification only)**

If smoke tests revealed code changes, those changes get their own commit on the appropriate task above.
