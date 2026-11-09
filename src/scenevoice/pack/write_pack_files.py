import os
from pathlib import Path

from scenevoice.pack.manifest_name import MANIFEST_NAME
from scenevoice.pack.timeline_name import TIMELINE_NAME
from scenevoice.pack.write_temp_file import write_temp_file


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def write_pack_files(directory: str | Path, manifest: bytes, timeline: bytes) -> str | None:
    """Write DIR/scene_manifest.csv and DIR/resolve_timeline.otio from temp files, manifest renamed first.

    Failure removes only files this run created (temp files, and the manifest if the timeline rename fails).
    Returns None on success, or a one-line message naming the failing file; never raises OSError.
    """
    temps: list[str] = []
    renamed_manifest = None
    failing = MANIFEST_NAME
    try:
        temps.append(write_temp_file(directory, manifest))
        failing = TIMELINE_NAME
        temps.append(write_temp_file(directory, timeline))
        failing = MANIFEST_NAME
        manifest_path = os.path.join(directory, MANIFEST_NAME)
        os.replace(temps[0], manifest_path)
        renamed_manifest = manifest_path
        failing = TIMELINE_NAME
        os.replace(temps[1], os.path.join(directory, TIMELINE_NAME))
        return None
    except OSError:
        for temp in temps:
            _remove(temp)
        if renamed_manifest is not None:
            _remove(renamed_manifest)
        return f"could not write {failing}"
