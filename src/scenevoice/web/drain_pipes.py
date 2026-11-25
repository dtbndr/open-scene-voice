import threading
from collections.abc import Callable
from typing import IO

from .drain import Drain
from .line_splitter import LineSplitter
from .stdout_capture import StdoutCapture

_CHUNK = 65536


def drain_pipes(
    stdout: IO[bytes],
    stderr: IO[bytes],
    on_line: Callable[[str], None],
    *,
    stdout_limit: int = 262144,
    line_limit: int = 65536,
) -> Drain:
    """Start two threads that read both pipes to end of file, so neither can fill while the other is read.

    Stdout keeps its first `stdout_limit` bytes and counts the rest; stderr goes to `on_line` split on newlines only.
    A failing `on_line` never stops the drain (a stalled drain would hold the child's pipes and the job slot).
    """
    capture: list[StdoutCapture] = [StdoutCapture(b"", 0)]

    def read_stdout() -> None:
        kept = bytearray()
        total = 0
        while chunk := stdout.read1(_CHUNK):  # type: ignore[attr-defined]
            total += len(chunk)
            kept += chunk[: max(0, stdout_limit - len(kept))]
        capture[0] = StdoutCapture(bytes(kept), total)

    def deliver(lines: list[str]) -> None:
        for line in lines:
            try:
                on_line(line)
            except Exception:  # noqa: BLE001 - an observer bug must not stall the drain
                pass

    def read_stderr() -> None:
        splitter = LineSplitter(line_limit)
        while chunk := stderr.read1(_CHUNK):  # type: ignore[attr-defined]
            deliver(splitter.feed(chunk))
        deliver(splitter.finish())

    threads = [threading.Thread(target=read_stdout, daemon=True), threading.Thread(target=read_stderr, daemon=True)]
    for thread in threads:
        thread.start()
    return Drain(threads, capture)
