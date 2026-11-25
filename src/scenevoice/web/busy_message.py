_MESSAGES = {
    "synth": "SceneVoice is busy voicing.",
    "synth-scene": "SceneVoice is busy voicing.",
    "beats": "SceneVoice is busy planning visual beats.",
    "beats-redo": "SceneVoice is busy planning visual beats.",
    "align": "SceneVoice is busy updating line markers.",
    "pack": "SceneVoice is busy packing.",
    "download": "SceneVoice is busy preparing a download.",
    "stopping": "SceneVoice is stopping.",
}


def busy_message(reason: str | None) -> str:
    """The J12 busy wording for the reason `JobRunner.busy_reason()` gives (a running kind, a download or a shutdown)."""
    return _MESSAGES.get(reason or "", _MESSAGES["synth"])
