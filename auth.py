import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

DEFAULT_TOKEN_PATH = Path.home() / ".config" / "claude-gmail-mcp" / "token.json"


def _token_path() -> Path:
    override = os.environ.get("GMAIL_TOKEN_PATH")
    return Path(override) if override else DEFAULT_TOKEN_PATH


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(
            "Usage: claude-gmail-mcp-auth <path/to/credentials.json>\n"
            "\n"
            "Runs a one-time OAuth browser flow and writes a refresh token to\n"
            f"  {DEFAULT_TOKEN_PATH}\n"
            "(or to $GMAIL_TOKEN_PATH if set).",
            file=sys.stderr,
        )
        return 2

    credentials_path = Path(argv[0])
    if not credentials_path.is_file():
        print(f"Error: credentials file not found: {credentials_path}", file=sys.stderr)
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    out = _token_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(creds.to_json())
    out.chmod(0o600)

    print(f"Token written to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
