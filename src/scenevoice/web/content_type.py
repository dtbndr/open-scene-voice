CONTENT_TYPES = {
    "html": "text/html; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "svg": "image/svg+xml",
    "png": "image/png",
    "ico": "image/x-icon",
    "woff2": "font/woff2",
    "txt": "text/plain; charset=utf-8",
    "map": "application/json; charset=utf-8",
}


def content_type(name: str) -> str | None:
    """A fixed constant per extension; None means the file is never served (no octet-stream fallback)."""
    _, dot, extension = name.rpartition(".")
    return CONTENT_TYPES.get(extension.lower()) if dot else None
