from collections.abc import Callable


def say_scene(
    say: Callable[..., None], json_mode: bool, state: str, ordinal: int, total: int, message: str
) -> None:
    """One scene event (JSON mode only; text mode writes no per-scene lines); align has no `path`."""
    if json_mode:
        say(message, event="scene", state=state, scene=ordinal, total=total)
