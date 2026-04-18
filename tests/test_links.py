import pytest

import links


def test_gmail_url_uses_email_in_user_slot():
    url = links.gmail_url("16f3a2b4c5d6e7f8", "alice@example.com")
    assert url == "https://mail.google.com/mail/u/alice@example.com/#all/16f3a2b4c5d6e7f8"


def test_gmail_url_handles_plus_alias():
    url = links.gmail_url("abc123", "alice+work@example.com")
    assert url == "https://mail.google.com/mail/u/alice+work@example.com/#all/abc123"


def test_msgid_decimal_to_hex_accepts_int():
    assert links.msgid_decimal_to_hex(1655752825319194624) == "16fa6a6c0d000000"


def test_msgid_decimal_to_hex_accepts_str():
    assert links.msgid_decimal_to_hex("1655752825319194624") == "16fa6a6c0d000000"


def test_msgid_hex_to_decimal_round_trip():
    decimal = "1655752825319194624"
    hex_form = links.msgid_decimal_to_hex(decimal)
    assert links.msgid_hex_to_decimal(hex_form) == decimal


def test_msgid_hex_to_decimal_strips_optional_0x_prefix():
    assert links.msgid_hex_to_decimal("0x16fa6a6c0d000000") == "1655752825319194624"


def test_msgid_hex_to_decimal_accepts_uppercase():
    assert links.msgid_hex_to_decimal("16FA6A6C0D000000") == "1655752825319194624"
