import os
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Fast liveness health probe."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok", "live": True})


class ReadinessCheckView(APIView):
    """Readiness probe checking database, cache, and filesystem storage."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        checks = {}
        all_ok = True

        # Database Check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {str(exc)}"
            all_ok = False

        # Cache Check
        try:
            cache_key = "health:ready:test"
            cache.set(cache_key, "1", timeout=10)
            val = cache.get(cache_key)
            if val == "1":
                checks["cache"] = "ok"
            else:
                checks["cache"] = "unresponsive"
                all_ok = False
        except Exception as exc:
            checks["cache"] = f"error: {str(exc)}"
            all_ok = False

        # Storage Check
        media_root = getattr(settings, "MEDIA_ROOT", None)
        if media_root:
            try:
                os.makedirs(media_root, exist_ok=True)
                test_path = os.path.join(media_root, ".ready_test")
                with open(test_path, "w") as f:
                    f.write("ok")
                if os.path.exists(test_path):
                    os.remove(test_path)
                checks["storage"] = "ok"
            except Exception as exc:
                checks["storage"] = f"error: {str(exc)}"
                all_ok = False
        else:
            checks["storage"] = "unconfigured"

        resp_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(
            {
                "status": "ok" if all_ok else "unhealthy",
                "ready": all_ok,
                "checks": checks,
            },
            status=resp_status,
        )
