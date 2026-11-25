from .job_request import JobRequest
from .parse_confirm import parse_confirm
from .valid_text import valid_text

_TEXT = ("voice", "model", "language", "instruction")
_KEYS = {
    "synth": {"mode", *_TEXT, "confirm"},
    "synth-scene": {"scene", *_TEXT, "confirm"},
    "beats": {"model", "confirm"},
    "beats-redo": {"model", "confirm"},
    "align": {"confirm"},
    "pack": set(),
}
_MODES = ("all", "rest", "restart")


def _required(kind: str, mode: str | None) -> set[str]:
    if kind == "synth":
        return {"voice", "model"} if mode in ("all", "restart") else set()
    return {"model"} if kind in ("beats", "beats-redo") else set()


def parse_job_request(body: object) -> JobRequest | None:
    """The start request of `POST /api/projects/{id}/jobs`, or None for any body that is not exactly one known shape.

    Looks at the body alone (never the project): kinds, required and optional fields, strict types (a boolean is
    not an integer), text of 1 to 1000 characters without NUL, unknown keys, and the confirmation of a paid kind.
    """
    if not isinstance(body, dict):
        return None
    kind = body.get("kind")
    if not isinstance(kind, str) or kind not in _KEYS or set(body) - _KEYS[kind] - {"kind"}:
        return None
    mode = body.get("mode")
    if kind == "synth" and mode not in _MODES:
        return None
    scene = body.get("scene")
    if kind == "synth-scene" and (type(scene) is not int or scene < 1):
        return None
    if any(key in body and not valid_text(body[key]) for key in _TEXT) or not _required(kind, mode) <= set(body):
        return None
    confirm = None
    if kind != "pack":
        confirm = parse_confirm(body.get("confirm"), with_model=kind != "align", with_characters=kind != "align")
        if confirm is None:
            return None
    voice, model, language, instruction = (body.get(key) for key in _TEXT)
    return JobRequest(kind, mode, scene, voice, model, language, instruction, confirm)
