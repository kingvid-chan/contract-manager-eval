"""Middleware for FastAPI application."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Add Cache-Control: no-cache to all HTML responses.

    Per CLAUDE.md constraint: HTML documents must carry real
    Cache-Control: no-cache HTTP response header (not <meta> tag).
    """

    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-cache"
        return response
