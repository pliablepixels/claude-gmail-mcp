# claude-gmail-mcp

[![PyPI](https://img.shields.io/pypi/v/claude-gmail-mcp)](https://pypi.org/project/claude-gmail-mcp/)

A super tiny Gmail MCP server for Claude Code. Lets Claude send, search, and read Gmail on your behalf.

Two backends are supported and auto-selected at startup:

- **Gmail API (OAuth)** — recommended. No app password. Batch search. Direct Gmail web URLs on every result.
- **SMTP/IMAP (app password)** — simpler setup. Fallback when the OAuth token isn't present.

I needed something for my projects — there were a bunch around which seemed super complicated. So why not have Claude CLI build one for me :-p

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- One of:
  - A Google Cloud OAuth client (Desktop app) — for the API backend, OR
  - A Gmail [App Password](https://myaccount.google.com/apppasswords) — for the SMTP/IMAP backend

## Install (Gmail API backend — recommended)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project, enable the Gmail API, and configure the OAuth consent screen (External, add your Gmail as a test user). Create an OAuth client of type **Desktop app** and download the credentials JSON.
2. Run the auth helper, pointing at the downloaded file:

   ```sh
   uvx --from claude-gmail-mcp claude-gmail-mcp-auth /path/to/credentials.json
   ```

   Browser opens → sign in → approve (scope: `gmail.modify`). Refresh token is saved to `~/.config/claude-gmail-mcp/token.json` (perms `600`).
3. Register the MCP server with Claude Code (no env vars needed):

   ```sh
   claude mcp add gmail --scope user -- uvx claude-gmail-mcp
   ```

## Install (SMTP/IMAP backend — fallback)

```sh
claude mcp add gmail --scope user \
  -e GMAIL_ADDRESS=you@gmail.com \
  -e GMAIL_APP_PASSWORD=your-app-password \
  -- uvx claude-gmail-mcp
```

Replace `you@gmail.com` and `your-app-password` with your actual credentials. Drop `--scope user` to install only for the current project directory.

## Verify

```sh
claude mcp list
```

You should see `gmail` listed as a configured server. To see which backend is active, run:

```sh
uvx claude-gmail-mcp 2>&1 | head -1
```

Expected: `[gmail-mcp] backend=api` or `[gmail-mcp] backend=imap`. Ctrl-C to exit.

## Backend selection

At startup the server picks exactly one backend:

1. Token file at `GMAIL_TOKEN_PATH` (default `~/.config/claude-gmail-mcp/token.json`) exists → **API backend**.
2. Else `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` env vars set → **IMAP backend**.
3. Else tools return a "no backend configured" error.

To force a switch to the IMAP backend when a token file exists, set `GMAIL_TOKEN_PATH` to a non-existent path (or delete the token file).

## Usage

Ask Claude to send an email:

> Send an email to alice@example.com with subject "Hello" and body "Hi from Claude!"

Tools exposed:

- **`send_email`** — `to`, `subject`, `body`, optional `cc`/`bcc`, `html`, `attachments` (local file paths; unreadable files are skipped with a warning).
- **`search_emails`** — `queries` (single string or list of strings), `max_results` (per query when a list is passed). Results include the Gmail message ID in hex and a direct Gmail web URL per hit.
- **`read_email`** — `uid` (the hex ID from `search_emails`). Output includes the Gmail web URL at the top.

Batch search example:

> Search Gmail for "is:unread from:alice" and "is:unread from:bob" — show me both side by side.

Claude passes both queries in a single tool call. The response is sectioned per query. API backend executes the list step in one HTTP roundtrip; IMAP backend iterates.

Attachment example:

> Send an email to alice@example.com with subject "Report" and attach ~/Documents/report.pdf

## Publishing to PyPI

```sh
python -m build && twine upload dist/*
```

## For Development

```sh
git clone https://github.com/pliablepixels/claude-gmail-mcp.git
cd claude-gmail-mcp
uv sync
uv run pytest
```

Run the server locally:

```sh
uv run claude-gmail-mcp
```

Test with Claude Code using your local copy instead of the published package:

```sh
claude mcp add gmail --scope user \
  -- uv run --directory /path/to/claude-gmail-mcp claude-gmail-mcp
```

(For the IMAP backend add `-e GMAIL_ADDRESS=... -e GMAIL_APP_PASSWORD=...`.)
