import os
import smtplib
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
) -> str:
    """Send an email via Gmail SMTP.

    Args:
        to: Recipient email address(es).
        subject: Email subject line.
        body: Email body content (plain text or HTML).
        cc: CC recipient(s), optional.
        bcc: BCC recipient(s), optional.
        html: If True, send body as HTML instead of plain text.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return "Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables must be set."

    # Normalize recipients to lists
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
        return f"Email sent successfully to {recipient_summary} with subject '{subject}'."
    except smtplib.SMTPAuthenticationError:
        return "Error: Authentication failed. Check your GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
    except Exception as e:
        return f"Error sending email: {e}"


if __name__ == "__main__":
    mcp.run()
