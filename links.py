def gmail_url(message_id_hex: str, account_email: str) -> str:
    return f"https://mail.google.com/mail/u/{account_email}/#all/{message_id_hex}"


def msgid_decimal_to_hex(msgid: int | str) -> str:
    return format(int(msgid), "x")


def msgid_hex_to_decimal(msgid_hex: str) -> str:
    cleaned = msgid_hex.lower().removeprefix("0x")
    return str(int(cleaned, 16))
