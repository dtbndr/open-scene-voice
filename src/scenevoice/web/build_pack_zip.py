import io
import os
import time
import zipfile
from pathlib import Path

from .list_audio_names import list_audio_names
from .open_regular_file import open_regular_file
from .regular_file import regular_file
from .workspace_error import FileTooLargeError, NothingPackedError, PackTooLargeError

# The top-level pack outputs the zip may hold, the ONE constant: the first is required, the rest are optional.
# `audio/NNN.wav` files are the only other allowlisted entries (`audio_file_name`).
PACK_OUTPUTS = ("scene_manifest.csv", "resolve_timeline.otio")
PACK_CAP = 1024 * 1024 * 1024
ZIP_MIN_TIME = 315532800  # 1980-01-01 00:00:00 UTC, the earliest a zip can record
ZIP_MAX_TIME = 4354819198  # 2107-12-31 23:59:58 UTC, the latest


def _zip_time(mtime: float) -> tuple[int, int, int, int, int, int]:
    clamped = int(min(max(mtime, ZIP_MIN_TIME), ZIP_MAX_TIME))
    moment = time.gmtime(clamped)
    return (moment.tm_year, moment.tm_mon, moment.tm_mday, moment.tm_hour, moment.tm_min, moment.tm_sec)


def _read_upto(fd: int, size: int) -> tuple[bytes, float]:
    mtime = os.fstat(fd).st_mtime
    chunks: list[bytes] = []
    while size > 0:
        chunk = os.read(fd, min(size, 1024 * 1024))
        if not chunk:
            break
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks), mtime


def _measure(path: Path | None, cap: int, key_file: Path | None) -> int | None:
    """The fstat size of an acceptable file, or None; the descriptor is closed before returning."""
    if path is None:
        return None
    opened = open_regular_file(path, cap, key_file)
    if opened is None:
        return None
    os.close(opened[0])
    return opened[1]


def _read_file(path: Path, size: int, cap: int, key_file: Path | None) -> tuple[bytes, float] | None:
    """Reopen through the same checks and read at most `size` bytes; None when refused or gone."""
    opened = open_regular_file(path, cap, key_file)
    if opened is None:
        return None
    try:
        return _read_upto(opened[0], size)
    except OSError:
        return None
    finally:
        os.close(opened[0])


def build_pack_zip(directory: Path, project_id: str, key_file: Path | None, cap: int = PACK_CAP) -> bytes:
    """The in-memory zip of the allowlisted pack files of `directory`, under a top-level `<project_id>/` folder.

    Every file goes through `regular_file` and `open_regular_file`, so a symlink, a second hard link, a differently
    spelled name or the key file leaves it out. A refused manifest is `NothingPackedError`; a total over `cap` is
    `PackTooLargeError`, decided from `fstat` sizes before anything is read. Pass one measures each file, pass two
    reopens and reads it, so at most one descriptor is open at a time (a project with hundreds of WAVs must not hit
    the open-file limit and silently lose files). A file that opened in pass one but is refused or gone in pass two
    is left out (the manifest: nothing packed). Writes nothing.
    """
    required = PACK_OUTPUTS[0]
    entries = [(name, regular_file(directory, name, key_file=key_file)) for name in PACK_OUTPUTS]
    entries += [(f"audio/{name}", regular_file(directory, "audio", name, key_file=key_file)) for name in list_audio_names(directory)]
    measured: list[tuple[str, Path, int]] = []
    total = 0
    for name, path in entries:
        try:
            size = _measure(path, cap, key_file)
        except FileTooLargeError:
            raise PackTooLargeError(f"{name} holds more than {cap} bytes") from None
        if size is None or path is None:
            if name == required:
                raise NothingPackedError(required)
            continue
        total += size
        if total > cap:
            raise PackTooLargeError(f"the pack holds more than {cap} bytes")
        measured.append((name, path, size))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, path, size in sorted(measured):
            try:
                got = _read_file(path, size, cap, key_file)
            except FileTooLargeError:
                got = None
            if got is None:
                if name == required:
                    raise NothingPackedError(required)
                continue
            info = zipfile.ZipInfo(f"{project_id}/{name}", _zip_time(got[1]))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            archive.writestr(info, got[0])
    return buffer.getvalue()
