"""Shared stream test doubles: a recording wfile and a generator that records being closed."""

from collections.abc import Iterator


class RecordingWfile:
    def __init__(self, fail_on_write: int | None = None, error: BaseException | None = None) -> None:
        self.events: list[tuple[str, bytes]] = []
        self.writes = 0
        self.fail_on_write = fail_on_write
        self.error = error

    def write(self, data: bytes) -> int:
        self.writes += 1
        if self.fail_on_write == self.writes:
            raise self.error or BrokenPipeError()
        self.events.append(("write", data))
        return len(data)

    def flush(self) -> None:
        self.events.append(("flush", b""))

    def written(self) -> bytes:
        return b"".join(data for kind, data in self.events if kind == "write")


class ClosingChunks:
    """An iterator over chunks that records starts, closes and optionally raises after the chunks."""

    def __init__(self, chunks: list[bytes], raises: BaseException | None = None) -> None:
        self.pending = iter(chunks)
        self.raises = raises
        self.started = False
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        self.started = True
        try:
            return next(self.pending)
        except StopIteration:
            if self.raises is not None:
                raise self.raises from None
            raise

    def close(self) -> None:
        self.closed = True
