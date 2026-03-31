# Attachment Support for Gmail MCP Server

**Date:** 2026-03-31

## Summary

Add file attachment support to the `send_email` tool in `server.py`. Callers pass local file paths; missing or unreadable files are skipped with a warning rather than aborting the send.

## Changes

### `send_email` signature

Add one optional parameter:

```python
attachments: list[str] | None = None
```

Each element is a filesystem path (absolute or relative). The filename used in the email is `os.path.basename(path)`.

### Attachment processing

For each path in `attachments`:
- If the file exists and is readable: read it in binary mode, wrap in `MIMEBase('application', 'octet-stream')`, encode with `email.encoders.encode_base64`, set `Content-Disposition: attachment; filename=<basename>`, and attach to the message.
- If the file does not exist or cannot be read: skip it and record a warning string.

### Return value

The existing return string is extended to append any warnings:

```
"Email sent successfully to foo@example.com with subject 'Hi'. Warning: could not attach '/tmp/missing.pdf' (file not found)."
```

One warning clause per skipped file, appended in order.

## Imports

Two stdlib additions (no new dependencies):
- `from email.mime.base import MIMEBase`
- `from email import encoders`

## Error handling

- Missing/unreadable files: skip + warn (never abort the send).
- SMTP errors: unchanged from current behavior.
