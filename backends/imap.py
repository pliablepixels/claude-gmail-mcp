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
