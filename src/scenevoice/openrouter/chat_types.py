from collections.abc import Callable

Chat = Callable[[bytes], bytes]
"""(request body bytes) -> raw 200 response body; raises ChatError otherwise."""

ChatFactory = Callable[[str], Chat]
"""(API key) -> Chat; makes no network call."""
