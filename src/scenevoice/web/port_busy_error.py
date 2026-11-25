class PortBusyError(Exception):
    """Another program already listens on the port; the message is plain words for `web` to print."""
