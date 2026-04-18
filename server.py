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
