import threading

from .stdout_capture import StdoutCapture


class Drain:
    """Two reader threads that are already running; `join` waits for both pipes to reach end of file."""

    def __init__(self, threads: list[threading.Thread], capture: list[StdoutCapture]) -> None:
        self._threads = threads
        self._capture = capture

    def join(self, timeout: float | None = None) -> StdoutCapture:
        """The stdout capture once both pipes are at EOF; `TimeoutError` if they are not within `timeout`."""
        for thread in self._threads:
            thread.join(timeout)
        if any(thread.is_alive() for thread in self._threads):
            raise TimeoutError("the child's pipes are still open")
        return self._capture[0]
