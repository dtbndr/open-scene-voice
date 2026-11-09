def wav_name(ordinal: int) -> str:
    """The only place the three-digit output naming rule lives."""
    return f"{ordinal:03d}.wav"
