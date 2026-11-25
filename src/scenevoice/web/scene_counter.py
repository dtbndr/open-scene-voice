import threading


class SceneCounter:
    """Thread-safe count of finished scenes: the commit point `on_finish` reads (the observer notes each scene)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0

    def note(self) -> None:
        with self._lock:
            self._count += 1

    def value(self) -> int:
        with self._lock:
            return self._count

    def reset(self) -> None:
        with self._lock:
            self._count = 0
