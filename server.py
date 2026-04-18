import sys

from mcp.server.fastmcp import FastMCP

import backends

mcp = FastMCP("gmail")

# Lazy initialization: backend is set on first function call
_backend = None
_backend_initialized = False


def _ensure_backend_initialized():
    global _backend, _backend_initialized
    if not _backend_initialized:
        _backend = backends.detect_backend()
        _backend_initialized = True
        if _backend is None:
            print(
                "[gmail-mcp] no backend configured: set GMAIL_ADDRESS+GMAIL_APP_PASSWORD, "
                "or run 'uvx claude-gmail-mcp-auth <credentials.json>'",
                file=sys.stderr,
            )
        else:
            print(f"[gmail-mcp] backend={_backend.__name__.split('.')[-1]}", file=sys.stderr)


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
    _ensure_backend_initialized()
    if _backend is None:
        return _NO_BACKEND_MSG
    return _backend.send_email(to, subject, body, cc=cc, bcc=bcc, html=html, attachments=attachments)


@mcp.tool()
def search_emails(query: str, max_results: int = 10) -> str:
    """Search Gmail using full Gmail search syntax (from:, subject:, is:unread, etc).
    Returns UID, sender, subject, and date for each match.

    Args:
        query: Gmail search query, e.g. 'is:unread subject:invoice'
        max_results: Max emails to return (default 10)
    """
    _ensure_backend_initialized()
    if _backend is None:
        return _NO_BACKEND_MSG
    return _backend.search_emails(query, max_results=max_results)


@mcp.tool()
def read_email(uid: str) -> str:
    """Fetch the full content of an email by its UID (from search_emails results).

    Args:
        uid: Email UID shown in search_emails output
    """
    _ensure_backend_initialized()
    if _backend is None:
        return _NO_BACKEND_MSG
    return _backend.read_email(uid)


if __name__ == "__main__":
    mcp.run()
