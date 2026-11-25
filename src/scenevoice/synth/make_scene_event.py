from collections.abc import Callable


def make_scene_event(say: Callable[..., None]) -> Callable[[str, int, int, str | None, str], None]:
    """The synth_scenes `scene_event` callback writing scene events through `say` (JSON mode)."""

    def scene_event(state: str, ordinal: int, total: int, path: str | None, message: str) -> None:
        fields: dict[str, object] = {"event": "scene", "state": state, "scene": ordinal, "total": total}
        if path is not None:
            fields["path"] = path
        say(message, **fields)

    return scene_event
