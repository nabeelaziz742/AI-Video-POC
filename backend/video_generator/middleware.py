import logging
import time
import uuid
from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger("video_generator.request")


class RequestIDMiddleware:
    """Attaches a unique Request ID to each incoming request and response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class ProductionErrorMiddleware:
    """Catches unhandled exceptions in production and returns a clean JSON error response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        request_id = getattr(request, "id", "unknown")
        logger.error(
            "Unhandled server error on %s %s [RequestID: %s]: %s",
            request.method,
            request.path,
            request_id,
            exception,
            exc_info=True,
        )
        if not settings.DEBUG:
            response = JsonResponse(
                {
                    "detail": "An unexpected server error occurred.",
                    "request_id": request_id,
                },
                status=500,
            )
            response["X-Request-ID"] = request_id
            return response
        return None


class RequestLoggingMiddleware:
    """Logs incoming API requests with timing and request ID context."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        request_id = getattr(request, "id", "-")
        user_ident = getattr(getattr(request, "user", None), "username", "anonymous")
        logger.info(
            "%s %s -> %s (%sms) [user: %s, req: %s]",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            user_ident,
            request_id,
        )
        return response
