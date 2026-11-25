"""The child's progress vocabulary as the server needs it; a drift test compares these to `scenevoice.progress`."""

COMMANDS = ("plan", "synth", "align", "pack", "beats")
EVENT_NAMES = ("scene", "note", "ok", "fail")
SCENE_STATES = ("started", "done")
FAILURE_KINDS = ("missing_key", "bad_key", "quota", "provider_down", "invalid_input", "other")
FIXED_FAILURE = "SceneVoice could not finish. Try again."
MESSAGE_LIMIT = 1000
