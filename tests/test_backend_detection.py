import pytest

import backends
from backends import imap as imap_backend


def test_detect_returns_imap_when_app_password_env_set(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_ADDRESS", "you@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "missing.json"))
    assert backends.detect_backend() is imap_backend


def test_detect_returns_none_when_nothing_configured(monkeypatch, tmp_path):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "missing.json"))
    assert backends.detect_backend() is None


def test_detect_returns_none_when_only_address_set(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_ADDRESS", "you@example.com")
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "missing.json"))
    assert backends.detect_backend() is None


def test_detect_returns_api_when_token_file_exists(monkeypatch, tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(
        '{"refresh_token":"x","client_id":"y","client_secret":"z","token_uri":"https://example/token","scopes":["scope"]}'
    )
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_file))

    from backends import api as api_backend
    assert backends.detect_backend() is api_backend


def test_detect_prefers_api_over_imap_when_both_present(monkeypatch, tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text(
        '{"refresh_token":"x","client_id":"y","client_secret":"z","token_uri":"https://example/token","scopes":["scope"]}'
    )
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token_file))
    monkeypatch.setenv("GMAIL_ADDRESS", "you@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

    from backends import api as api_backend
    assert backends.detect_backend() is api_backend
