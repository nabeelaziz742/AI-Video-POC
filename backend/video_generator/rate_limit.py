from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status


def allow_request(request, key_prefix: str, limit: int = 20, window: int = 60) -> bool:
    """Small cache-backed guard for expensive endpoints. Returns False after limit/window."""
    ident = request.META.get("REMOTE_ADDR", "unknown")
    key = f"video:{key_prefix}:{ident}"
    try:
        count = cache.get(key, 0)
        if count >= limit:
            return False
        cache.set(key, count + 1, timeout=window)
        return True
    except Exception:
        # Availability-first: don't take the whole API down if cache is unavailable.
        return True


def rate_limited_response():
    return Response({"detail": "Too many requests. Please try again shortly."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
