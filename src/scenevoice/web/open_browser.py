from collections.abc import Callable


def open_browser(opener: Callable[[str], object], link: str) -> None:
    """Best effort: a failing or false-returning opener is fine because the link is already printed."""
    try:
        opener(link)
    except Exception:
        return
