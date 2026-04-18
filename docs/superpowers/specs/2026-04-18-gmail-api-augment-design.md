# Gmail API backend (augment SMTP/IMAP)

**Status:** Approved spec, awaiting implementation plan
**Date:** 2026-04-18

## Summary

Add a Gmail API backend alongside the existing SMTP/IMAP backend. Backend is auto-selected at startup based on whether OAuth credentials are present. Tool surface stays identical to today (`send_email`, `search_emails`, `read_email`), with two functional improvements that apply to both backends: `search_emails` accepts a list of queries, and every search/read result includes a Gmail web URL.

## Goals

- Preserve the current SMTP/IMAP path unchanged for users who don't want OAuth.
- Offer Gmail API as a no-config-flag opt-in: if a token exists, use it.
- Reach functional parity for the three existing tools — no new tools in v1.
- Make `search_emails` callable with multiple queries in one tool invocation.
- Surface a direct Gmail web URL for each message returned.

## Non-goals

- Label modification, drafts, threads, history, push notifications. Deferred to a later release once the OAuth foundation is solid.
- Replacing or deprecating the SMTP/IMAP path.
- Service-account or domain-wide-delegation auth. Personal user OAuth only.
- Shipping a public OAuth client. Users bring their own GCP project.

## Backend selection

Decided at startup, logged once, never switched per call.

Order of detection:
1. Token file at `GMAIL_TOKEN_PATH` (default `~/.config/claude-gmail-mcp/token.json`) exists and loads as valid `google.oauth2.credentials.Credentials` → **API backend**.
2. Else `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` env vars set → **IMAP backend**.
3. Else **no backend**: server still starts (so `claude mcp list` shows it healthy), but every tool returns `"No backend configured. Set GMAIL_ADDRESS+GMAIL_APP_PASSWORD, or run 'uvx claude-gmail-mcp auth <credentials.json>'."`

Startup log line (stderr): `[gmail-mcp] backend=api (token=~/.config/claude-gmail-mcp/token.json, account=you@gmail.com)` or `backend=imap (account=you@gmail.com)`.

## OAuth setup

Users bring their own Google Cloud project. The `auth` subcommand handles the one-time browser flow.

- Invocation: `uvx claude-gmail-mcp auth /path/to/credentials.json`
  - `credentials.json` is the "Desktop app" OAuth client downloaded from GCP Console.
- Flow: `google-auth-oauthlib`'s `InstalledAppFlow.run_local_server()` — opens browser, captures auth code on a localhost callback, exchanges for refresh token.
- Scope: `https://www.googleapis.com/auth/gmail.modify` — forward-looking, avoids re-consent if future tools need to label/archive/draft.
- Output: writes `{refresh_token, client_id, client_secret, token_uri, scopes}` JSON to `GMAIL_TOKEN_PATH` (default `~/.config/claude-gmail-mcp/token.json`) with `chmod 600`. Creates the directory if missing. Overwrites cleanly on re-run.

Auto-refresh of access tokens is handled transparently by `google-auth`. If refresh fails, tools return: `"Auth failed — re-run 'uvx claude-gmail-mcp auth <credentials.json>'"`.

## Code organization

```
server.py             # Thin MCP tool layer. Detects backend at startup, dispatches.
auth.py               # `auth` subcommand: OAuth browser flow, writes token file.
links.py              # Shared: Gmail web URL construction, X-GM-MSGID hex conversion.
backends/__init__.py  # detect_backend() returns the active backend module.
backends/imap.py      # Refactored from current server.py — SMTP send + IMAP search/read.
backends/api.py       # New — Gmail API send/search/read.
```

Each backend module exposes the same three functions with the same signatures:
```python
def send_email(to, subject, body, cc=None, bcc=None, html=False, attachments=None) -> str
def search_emails(queries: str | list[str], max_results: int = 10) -> str
def read_email(uid: str) -> str
```

No abstract base class — duck typing is sufficient for two implementations. `server.py` resolves the backend module once and binds it to local names.

`links.py` is shared because both backends need to mint identical URLs.

The `auth` subcommand is registered as a separate console script (`pyproject.toml` `[project.scripts]`), or dispatched via `sys.argv[1] == "auth"` inside the existing entry point. Either is fine; implementation plan picks one.

## Tool shapes

### `send_email`

Identical signature and behavior to today. Both backends produce the same return string format.

API backend implementation: build a MIME message (reuse the existing MIMEMultipart construction from `imap.py`), base64url-encode the raw bytes, call `users.messages.send` with `{"raw": <encoded>}`. Attachments are added to the MIMEMultipart the same way as today, before encoding.

### `search_emails`

Signature changes:
```python
def search_emails(queries: str | list[str], max_results: int = 10) -> str
```

`max_results` is **per query** so a noisy query can't starve others.

String input → current single-section output, unchanged (backwards compatible).

List input → sectioned output:
```
=== Query: is:unread ===
[uid:16f3a2b4c5d6e7f8] 2026-04-18 | From: alice@example.com | Subject: Hello
  → https://mail.google.com/mail/u/you@gmail.com/#all/16f3a2b4c5d6e7f8

=== Query: from:bob ===
No messages found.
```

Note: `uid:` in the output now contains the Gmail message ID in hex (same value across both backends), not the IMAP UID. This is what `read_email` accepts. Backwards-compatibility note: existing users who depended on the IMAP UID format would see a change. Acceptable because the UID is opaque and only meaningful when fed back into `read_email`.

Backend behavior:
- IMAP: loop queries serially. Saves Claude tool-call roundtrips even though each query is a separate IMAP roundtrip.
- API: use `googleapiclient.http.BatchHttpRequest` to send all `users.messages.list` calls in one HTTP request.

### `read_email`

Signature unchanged: `read_email(uid: str) -> str`.

`uid` is the Gmail message ID in hex (returned by `search_emails`).

Output gains a Gmail web URL line at the top:
```
https://mail.google.com/mail/u/you@gmail.com/#all/<id>
From: ...
To: ...
Subject: ...
Date: ...

<body>
```

IMAP backend: convert the incoming hex ID to decimal, then fetch via the `X-GM-MSGID <decimal>` IMAP search criterion (Gmail extension — decimal-only). API backend: `users.messages.get(id=<hex>, format='full')`.

## Gmail web links

Format: `https://mail.google.com/mail/u/<gmail_address>/#all/<message_id_hex>`

Using the email address in the `u/` slot (instead of `u/0`) makes the URL work regardless of which slot the user's browser has assigned to the account. The address comes from:
- IMAP backend: `GMAIL_ADDRESS` env var.
- API backend: `users.getProfile()` called once at startup, result cached.

`links.py` exposes:
```python
def gmail_url(message_id_hex: str, account_email: str) -> str
def msgid_decimal_to_hex(msgid: int | str) -> str  # IMAP X-GM-MSGID fetch → web URL / search output
def msgid_hex_to_decimal(msgid_hex: str) -> str    # read_email uid input → IMAP X-GM-MSGID search
```

## Dependencies

Added to `pyproject.toml` `dependencies` (all required, not optional extras):
- `google-api-python-client`
- `google-auth`
- `google-auth-oauthlib`

Rationale: package is small, `uvx` makes install painless, and optional extras would force every user to remember the `[api]` syntax. Wheel grows by ~5 MB — acceptable.

## Error handling

| Condition | Response |
|-----------|----------|
| `RefreshError` (revoked/expired refresh token) | `"Auth failed — re-run 'uvx claude-gmail-mcp auth <credentials.json>'"` |
| `HttpError 401/403` | Same as above. |
| `HttpError 429` (rate limit) | `"Gmail API rate limit hit, try again shortly"`. No automatic retry. |
| `HttpError 5xx` | Bubble up the message verbatim. No automatic retry. |
| IMAP errors | Handled as today. |
| No backend at startup | Server starts; each tool returns the no-backend message. |

No retry/backoff logic in v1 — let Claude decide whether to retry.

## Testing

Add to existing `tests/` directory:
- `tests/test_backend_detection.py` — token file present/absent, env vars present/absent, precedence order. No real API calls.
- `tests/test_links.py` — `X-GM-MSGID` decimal→hex round-trip, URL format with various email addresses (including `+` aliases).
- `tests/test_batch_search.py` — string vs list input dispatch, output formatting, empty-result branches. Backend module mocked.
- `tests/test_api_backend.py` — mock `googleapiclient` calls, verify request shapes (queries sent to batch endpoint, message ID format, attachment encoding). No real Gmail.

The OAuth flow itself (`auth` subcommand) is not unit-tested — interactive browser flow is hard to mock meaningfully. Manual smoke test documented in the README's dev section.

## README updates

Add a section: "Using the Gmail API backend (optional)". Covers:
- Why someone might want it (no app password, batch search, message links).
- BYO GCP project setup: enable Gmail API, create Desktop OAuth client, download `credentials.json`.
- One-time `auth` command.
- MCP install command (no env vars needed if default token path is used).
- How to switch backends (delete the token file or set `GMAIL_TOKEN_PATH` to a non-existent path to fall back to IMAP).

## Open questions

None at spec time. All decisions resolved during brainstorming.

## Future work (deferred)

- `modify_labels` tool (archive, mark read, add/remove labels) — easy once API backend exists.
- `create_draft` / `list_drafts` tools.
- `auth --revoke` to clean up the token file.
- Optional retry/backoff on transient API errors.
