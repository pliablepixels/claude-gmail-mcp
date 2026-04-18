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
    ids_per_query: dict[str, list[str]] = {q: [] for q in query_list}

    service = _service()

    def _make_callback(query: str):
        def _cb(request_id, response, exception):
            if exception is not None:
                raise exception
            ids_per_query[query] = [m["id"] for m in response.get("messages", [])]
        return _cb

    batch = service.new_batch_http_request()
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
