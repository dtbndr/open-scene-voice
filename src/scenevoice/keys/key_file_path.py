import os
from collections.abc import Mapping
from pathlib import Path

_OVERRIDE = "SCENEVOICE_KEYS_FILE"


def key_file_path(
    environ: Mapping[str, str],
    *,
    os_name: str | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user key file path; `Path.home()` is read only if needed."""
    override = environ.get(_OVERRIDE, "")
    if override.strip():
        return Path(override)

    home_dir = home if home is not None else Path.home()
    if (os_name if os_name is not None else os.name) == "nt":
        appdata = environ.get("APPDATA", "")
        base = Path(appdata) if appdata.strip() else home_dir / "AppData" / "Roaming"
        return base / "scenevoice" / "keys.env"

    xdg = environ.get("XDG_CONFIG_HOME", "")
    if xdg.strip() and Path(xdg).is_absolute():
        return Path(xdg) / "scenevoice" / "keys.env"
    return home_dir / ".config" / "scenevoice" / "keys.env"
