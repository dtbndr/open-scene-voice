from http import HTTPStatus

from .security_headers import security_headers


def build_head(
    status: int, headers: tuple[tuple[str, str], ...], no_store: bool, length: int | None
) -> bytes:
    """Status line and headers; `length=None` (streaming) omits Content-Length. Always HTTP/1.0 with close."""
    try:
        phrase = HTTPStatus(status).phrase
    except ValueError:
        phrase = "Unknown"
    lines = [f"HTTP/1.0 {status} {phrase}"]
    lines += [f"{name}: {value}" for name, value in (*headers, *security_headers(no_store))]
    if length is not None:
        lines.append(f"Content-Length: {length}")
    lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
