import signal
import threading
from types import FrameType


def _stop_signals() -> list[signal.Signals]:
    return [signal.SIGINT, signal.SIGTERM, *([signal.SIGHUP] if hasattr(signal, "SIGHUP") else [])]


class StopSignals:
    """Turn SIGINT, SIGTERM and SIGHUP into a `KeyboardInterrupt` once, then ignore them until `restore`.

    The first signal swaps all three handlers for an ignoring one (the latch) and raises, so a second signal during
    the shutdown can neither interrupt the cleanup nor kill the process. `latch` does the same swap without raising,
    for a server that stopped for another reason. Handlers can only be set on the main thread; elsewhere `install`
    does nothing and returns False.
    """

    def __init__(self) -> None:
        self._previous: dict[signal.Signals, object] = {}
        self._latched = False

    def install(self) -> bool:
        if threading.current_thread() is not threading.main_thread():
            return False
        for each in _stop_signals():
            self._previous[each] = signal.signal(each, self._first)
        return True

    def latch(self) -> None:
        if not self._previous:
            return
        self._latched = True
        for each in self._previous:
            signal.signal(each, self._ignore)

    def restore(self) -> None:
        for each, handler in self._previous.items():
            if handler is not None:
                signal.signal(each, handler)  # type: ignore[arg-type]
        self._previous.clear()

    def _first(self, signum: int, frame: FrameType | None) -> None:
        if self._latched:
            return
        self.latch()
        raise KeyboardInterrupt

    def _ignore(self, signum: int, frame: FrameType | None) -> None:
        return None
