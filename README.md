# claude-gmail-mcp

[![PyPI](https://img.shields.io/pypi/v/claude-gmail-mcp)](https://pypi.org/project/claude-gmail-mcp/)

A super tiny Gmail MCP server for Claude Code. Lets Claude send emails on your behalf via Gmail SMTP.
I needed something for my projects - there were a bunch around which seemed super complicated. So why not
have claude CLI build one for me :-p


## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- A Gmail account with a generated [App Password](https://myaccount.google.com/apppasswords)

## Install

Add the MCP server to Claude Code (this will make it available to all projects):

```sh
claude mcp add gmail --scope user \
  -e GMAIL_ADDRESS=you@gmail.com \
  -e GMAIL_APP_PASSWORD=your-app-password \
  -- uvx claude-gmail-mcp
```

Replace `you@gmail.com` and `your-app-password` with your actual credentials.

To make it available to only the current project directory:

```sh
claude mcp add gmail \
  -e GMAIL_ADDRESS=you@gmail.com \
  -e GMAIL_APP_PASSWORD=your-app-password \
  -- uvx claude-gmail-mcp
```

## Verify

```sh
claude mcp list
```

You should see `gmail` listed as a configured server.

## Using the Gmail API backend (optional)

Instead of an app password, you can use an OAuth token and the Gmail API. With this backend:

- No app password required (OAuth-based auth).
- Batch search: pass a list of queries to `search_emails` and they run in one HTTP roundtrip.
- A direct Gmail web URL is included with every search/read result.

### One-time setup

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project, enable the Gmail API, and create an OAuth client of type **Desktop app**. Download the credentials JSON.
2. Run the auth helper, pointing at the downloaded file:

   ```sh
   uvx --from claude-gmail-mcp claude-gmail-mcp-auth /path/to/credentials.json
   ```

   This opens your browser, you grant access (scope: `gmail.modify`), and a refresh token is saved to `~/.config/claude-gmail-mcp/token.json`.
3. Add the MCP server (no env vars needed if the default token path is used):

   ```sh
   claude mcp add gmail --scope user -- uvx claude-gmail-mcp
   ```

The server picks the API backend automatically when the token file exists. Delete the token file (or set `GMAIL_TOKEN_PATH` to a missing path) to fall back to the SMTP/IMAP path.

### Batch search example

> Search Gmail for "is:unread from:alice" and "is:unread from:bob" — show me both lists side by side.

Claude will pass both queries in a single tool call, and the response will be sectioned per query.

## Usage

Once installed, ask Claude to send an email:

> Send an email to alice@example.com with subject "Hello" and body "Hi from Claude!"

Claude will use the `send_email` tool, which supports:

- **to** - recipient address(es)
- **subject** - email subject
- **body** - plain text or HTML body
- **cc/bcc** - optional CC/BCC recipients
- **html** - set to true to send HTML email
- **attachments** - list of local file paths to attach (files that can't be read are skipped with a warning)

`search_emails` accepts either a single query string or a list of query strings. With a list, results are sectioned per query and `max_results` applies per query.

Example with an attachment:

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
```

Run the server locally:

```sh
uv run claude-gmail-mcp
```

To test with Claude Code using your local copy instead of the published package:

```sh
claude mcp add gmail \
  -e GMAIL_ADDRESS=you@gmail.com \
  -e GMAIL_APP_PASSWORD=your-app-password \
  -- uv run --directory /path/to/claude-gmail-mcp claude-gmail-mcp
```
