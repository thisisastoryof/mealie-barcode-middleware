import unicodedata
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_for_display(text: str | None, max_len: int = 21) -> str | None:
    """Normalize Unicode for OLED display compatibility.

    Keeps common European characters (German, French, Nordic),
    degrades everything else to ASCII or '?'.
    """
    if text is None:
        return None
    KEEP_CHARS = set("\u00e4\u00f6\u00fc\u00df\u00c4\u00d6\u00dc\u00e9\u00e8\u00ea\u00eb\u00e0\u00e2\u00e7\u00e5\u00f8\u00e6\u00b0")
    result = []
    for ch in text:
        if ch.isascii() or ch in KEEP_CHARS:
            result.append(ch)
        else:
            decomposed = unicodedata.normalize('NFKD', ch)
            ascii_part = decomposed.encode('ascii', 'ignore').decode()
            result.append(ascii_part if ascii_part else '?')
    return ''.join(result)[:max_len]
