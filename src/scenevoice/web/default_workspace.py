from pathlib import Path


def default_workspace(home: Path) -> Path:
    """The folder SceneVoice uses when `SCENEVOICE_WORKSPACE` is unset."""
    return home / "Documents" / "SceneVoice"
