def security_headers(no_store: bool) -> tuple[tuple[str, str], ...]:
    """The headers every response carries; `Cache-Control: no-store` only for API and stale-link responses."""
    headers = (
        ("Referrer-Policy", "no-referrer"),
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Content-Security-Policy", "frame-ancestors 'none'"),
    )
    return (*headers, ("Cache-Control", "no-store")) if no_store else headers
