# Attachment Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `attachments: list[str] | None` parameter to `send_email` that attaches local files, skipping unreadable ones with a warning.

**Architecture:** All changes are in `server.py`. For each path in `attachments`, attempt to read it in binary mode; on success attach as `MIMEBase`; on failure record a warning. Append warnings to the return string after a successful send.

**Tech Stack:** Python 3.11 stdlib (`email.mime.base`, `email.encoders`, `os.path`), pytest, unittest.mock

---

### Task 1: Set up test infrastructure

**Files:**
- Create: `tests/test_server.py`

- [ ] **Step 1: Add pytest dev dependency**

```bash
uv add --dev pytest
```

Expected: `pyproject.toml` updated, `uv.lock` updated.

- [ ] **Step 2: Create test file with SMTP mock fixture**

Create `tests/test_server.py`:

```python
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
```

- [ ] **Step 3: Run the test file to verify the fixture loads without error**

```bash
uv run pytest tests/test_server.py -v
```

Expected: `no tests ran`, 0 errors (fixture-only file is fine).

- [ ] **Step 4: Commit**

```bash
git add tests/test_server.py pyproject.toml uv.lock
git commit -m "chore: add pytest dev dependency and test fixture"
```

---

### Task 2: Test and implement attachment with valid file

**Files:**
- Modify: `tests/test_server.py`
- Modify: `server.py`

- [ ] **Step 1: Write failing test for a valid attachment**

Append to `tests/test_server.py`:

```python
def test_send_with_valid_attachment(mock_smtp, tmp_path):
    attachment = tmp_path / "report.txt"
    attachment.write_text("hello")

    # Import here so env vars are already set
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
    # Confirm sendmail was called once
    mock_smtp.sendmail.assert_called_once()
    # Confirm the raw message contains the filename
    raw = mock_smtp.sendmail.call_args[0][2]
    assert "report.txt" in raw
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_server.py::test_send_with_valid_attachment -v
```

Expected: FAIL — `send_email() got an unexpected keyword argument 'attachments'`

- [ ] **Step 3: Implement attachments in server.py**

Replace the top imports block and `send_email` function in `server.py` with:

```python
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gmail")

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


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


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_server.py::test_send_with_valid_attachment -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: add file attachment support to send_email"
```

---

### Task 3: Test skip-and-warn behavior for missing files

**Files:**
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write failing tests for missing/unreadable files**

Append to `tests/test_server.py`:

```python
def test_missing_attachment_skipped_with_warning(mock_smtp):
    import importlib, server
    importlib.reload(server)

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

    import importlib, server
    importlib.reload(server)

    result = server.send_email(
        to="recipient@example.com",
        subject="Test",
        body="Body",
        attachments=[str(good), "/nonexistent/bad.pdf"],
    )

    assert "sent successfully" in result
    assert "Warning" in result
    assert "bad.pdf" in result
    raw = mock_smtp.sendmail.call_args[0][2]
    assert "good.txt" in raw


def test_no_attachments_no_warning(mock_smtp):
    import importlib, server
    importlib.reload(server)

    result = server.send_email(
        to="recipient@example.com",
        subject="Test",
        body="Body",
    )

    assert "sent successfully" in result
    assert "Warning" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_server.py::test_missing_attachment_skipped_with_warning tests/test_server.py::test_mixed_attachments_sends_valid_skips_missing tests/test_server.py::test_no_attachments_no_warning -v
```

Expected: all FAIL (implementation not yet present — but wait, we wrote it in Task 2). Actually these should PASS since implementation is already in place. If they pass, proceed.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_server.py
git commit -m "test: add coverage for missing/mixed attachment scenarios"
```
