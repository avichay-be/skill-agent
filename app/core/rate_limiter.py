"""Rate limiter configuration for the application."""

from fastapi import Request
from slowapi import Limiter


def get_client_ip(request: Request) -> str:
    """Get client IP address, checking X-Forwarded-For header for proxy support.

    When running behind a proxy/load balancer, the real client IP is in
    X-Forwarded-For header. Format: "client, proxy1, proxy2"
    We take the first IP (the original client).

    Falls back to request.client.host if no X-Forwarded-For header.
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Take the first IP (original client) from comma-separated list
        return x_forwarded_for.split(",")[0].strip()
    # Fallback to direct client address
    return request.client.host if request.client else "unknown"


# Create rate limiter instance with proxy-aware key function
limiter = Limiter(key_func=get_client_ip)
