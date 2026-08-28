import re
from urllib.parse import urlparse

SAFE_URL_SCHEMES = {"http", "https"}


def validate_safe_url(url: str | None, allow_empty: bool = True) -> bool:
    """Validates that a URL uses a safe web scheme (http/https) and is well-formed."""
    if not url:
        return allow_empty
    url_str = str(url).strip()
    if not url_str:
        return allow_empty
    try:
        parsed = urlparse(url_str)
        if parsed.scheme.lower() not in SAFE_URL_SCHEMES:
            return False
        if not parsed.netloc:
            return False
        return True
    except Exception:
        return False


def mask_secret(secret: str | None, visible_start: int = 4, visible_end: int = 4) -> str:
    """Safely masks a secret string for display in admin or system status panels."""
    if not secret:
        return ""
    s = str(secret).strip()
    if len(s) <= (visible_start + visible_end):
        return "***"
    return f"{s[:visible_start]}...{s[-visible_end:]}"
