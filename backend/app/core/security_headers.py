from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies baseline OWASP-style hardening headers to every response.

    None of these change application behaviour — they only tell the browser
    how to treat this origin's content (nosniff, DENY framing, no referrer
    leakage, no camera/mic/geo permissions).
    """

    # Content-Security-Policy is the main injection/XSS defence. It is
    # deliberately scoped to the app's real needs:
    #   - Vite build output is served from self ('self' scripts/styles).
    #   - React renders inline style attributes -> 'unsafe-inline' styles.
    #   - Space Grotesk / Plus Jakarta Sans load via Google Fonts CSS.
    #   - Firebase Auth SDK exchanges tokens against *.googleapis.com.
    _CONTENT_SECURITY_POLICY = (
        "default-src 'self';"
        " script-src 'self';"
        " style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;"
        " font-src 'self' data: https://fonts.gstatic.com;"
        " img-src 'self' data: blob:;"
        " connect-src 'self' https://*.googleapis.com https://accounts.google.com;"
        " worker-src 'self' blob:;"
        " object-src 'none';"
        " base-uri 'self';"
        " frame-src 'none';"
        " frame-ancestors 'none';"
        " form-action 'self'"
    )

    _DEFAULT_HEADERS = {
        "Content-Security-Policy": _CONTENT_SECURITY_POLICY,
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
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
