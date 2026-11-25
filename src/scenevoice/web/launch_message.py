from collections.abc import Sequence


def launch_message(link: str, ignored: Sequence[str]) -> list[str]:
    """The lines printed at launch; `ignored` holds variable NAMES only, never values."""
    lines = [
        "SceneVoice is running.",
        f"Open it here: {link}",
        "Keep this window open while you work. Closing it stops SceneVoice.",
        "To stop on purpose, press Control-C.",
    ]
    if ignored:
        lines.append(
            f"Not used here: {', '.join(ignored)} (set in this terminal). "
            "SceneVoice in the browser uses only saved keys; add them with scenevoice keys set."
        )
    return lines
