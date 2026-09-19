from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies baseline OWASP-style hardening headers to every response.

    None of these change application behaviour — they only tell the browser
    how to treat this origin's content (nosniff, DENY framing, no referrer
    leakage, no camera/mic/geo permissions).
    """

    _DEFAULT_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        for name, value in self._DEFAULT_HEADERS.items():
            response.headers.setdefault(name, value)
        return response
