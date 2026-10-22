"""Render external fields as data, not notification markup."""
import re
import unicodedata


def plain_text(value):
    text = ''.join(c for c in str(value) if c == '\n' or not unicodedata.category(c).startswith('C'))
    # Keep literal external URLs readable without creating automatic links.
    return re.sub(r'(?i)\b(https?|ftp)://', lambda m: m[1] + '∶//', text)


def card_text(value):
    return re.sub(r'([\\\[\]()*_~`<>#!|])', r'\\\1', plain_text(value))
