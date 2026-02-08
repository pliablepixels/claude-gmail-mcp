# claude-gmail-mcp

[![PyPI](https://img.shields.io/pypi/v/claude-gmail-mcp)](https://pypi.org/project/claude-gmail-mcp/)

A super tiny Gmail MCP server for Claude Code. Lets Claude send emails on your behalf via Gmail SMTP.
I needed something for my projects - there were a bunch around which seemed super complicated. So why not
have claude CLI build one for me :-p


## Prerequisites

- A Gmail account with a generated [App Password](https://myaccount.google.com/apppasswords)

## Install

```sh
pip install claude-gmail-mcp
```

Then add the MCP server to Claude Code:

```sh
claude mcp add gmail \
  -e GMAIL_ADDRESS=you@gmail.com \
  -e GMAIL_APP_PASSWORD=your-app-password \
  -- uvx claude-gmail-mcp
```

Replace `you@gmail.com` and `your-app-password` with your actual credentials.

To make it available across all projects, add `--scope user`:

```sh
claude mcp add gmail --scope user \
  -e GMAIL_ADDRESS=you@gmail.com \
  -e GMAIL_APP_PASSWORD=your-app-password \
  -- uvx claude-gmail-mcp
```

## Verify

```sh
claude mcp list
```

You should see `gmail` listed as a configured server.

## Usage

Once installed, ask Claude to send an email:

> Send an email to alice@example.com with subject "Hello" and body "Hi from Claude!"

Claude will use the `send_email` tool, which supports:

- **to** - recipient address(es)
- **subject** - email subject
- **body** - plain text or HTML body
- **cc/bcc** - optional CC/BCC recipients
- **html** - set to true to send HTML email
