from .record_item import RecordItem


def common_settings(items: tuple[RecordItem, ...]) -> dict[str, str | None] | None:
    """The voice, model, language and instruction every entry shares, or None with no entries or when they disagree."""
    settings = {(i.voice, i.model, i.language, i.instruction) for i in items}
    if len(settings) != 1:
        return None
    voice, model, language, instruction = settings.pop()
    return {"voice": voice, "model": model, "language": language, "instruction": instruction}
