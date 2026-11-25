from signal import SIGINT, SIGKILL

from .running_child import RunningChild


def stop_process_group(child: RunningChild, delay: float) -> None:
    """Interrupt the child's group, and kill it if the child has not exited `delay` seconds later.

    Blocks until the child has exited or the kill went out; the owner of `child` reaps it.
    """
    child.signal_group(SIGINT)
    if not child.exited.wait(delay):
        child.signal_group(SIGKILL)
