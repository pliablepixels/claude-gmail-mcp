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
