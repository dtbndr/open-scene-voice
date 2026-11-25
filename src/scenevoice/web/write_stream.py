from io import BufferedIOBase

from .start_stream import start_stream
from .stream_response import StreamResponse


def write_stream(wfile: BufferedIOBase, stream: StreamResponse, head_only: bool = False) -> None:
    """Head, then each chunk flushed; any failure after the head just ends the response. Always closes the iterator."""
    try:
        start_stream(wfile, stream.status, stream.headers, stream.no_store)
        if head_only:
            return
        for chunk in stream.chunks:
            wfile.write(chunk)
            wfile.flush()
    except Exception:
        return
    finally:
        close = getattr(stream.chunks, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                pass
