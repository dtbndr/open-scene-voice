import os
import subprocess
import threading
import time
from signal import SIGKILL

_POLL_SECONDS = 0.005


class RunningChild:
    """One child in its own process group, signalled only while it has not been reaped.

    Every `poll`, reap and group signal happens under one lock, so a signal can never reach a recycled pid. When
    `wait` sees the leader exit it kills whatever is left in the group (a stray grandchild would hold the pipes
    open and outlive the job) before anyone else can look at the child again; `exited` is set after that.
    """

    def __init__(self, proc: "subprocess.Popen[bytes]") -> None:
        self.proc = proc
        self.exited = threading.Event()
        self._lock = threading.Lock()

    def signal_group(self, sig: int) -> bool:
        """Send `sig` to the child's group if it is still unreaped; whether a signal was sent."""
        with self._lock:
            if self.proc.returncode is not None:
                return False
            return self._send(sig)

    def _send(self, sig: int) -> bool:
        try:
            os.killpg(self.proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return False
        return True

    def wait(self) -> int:
        """Block until the leader exits, sweep its group, and return the exit code."""
        while True:
            with self._lock:
                code = self.proc.poll()
                if code is not None:
                    self._send(SIGKILL)
                    break
            time.sleep(_POLL_SECONDS)
        self.exited.set()
        return code
