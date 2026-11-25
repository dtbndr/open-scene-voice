from io import BufferedIOBase

from .build_head import build_head


def start_stream(
    wfile: BufferedIOBase, status: int = 200, headers: tuple[tuple[str, str], ...] = (), no_store: bool = True
) -> None:
    """Interface for streaming (WS43): headers with no Content-Length; the caller writes the body and closes."""
    wfile.write(build_head(status, headers, no_store, None))
    wfile.flush()
