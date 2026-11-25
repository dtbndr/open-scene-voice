import os
from collections.abc import Callable
from pathlib import Path

from scenevoice.beats.path_exists_message import path_exists_message


def _write_to_descriptor(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(descriptor, view):]


def write_out_file(
    path: str | Path,
    text: str,
    *,
    command: str,
    write_bytes: Callable[[int, bytes], None] = _write_to_descriptor,
) -> str | None:
    """Create path exclusively (mode 0o666 minus umask) and write text as exact UTF-8 bytes.

    Returns None on success, or a one-line message; never raises OSError.
    Only a file this call created is unlinked when the write fails.
    """
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    except FileExistsError:
        return path_exists_message(path, command=command)
    except OSError as error:
        return f"could not create {path} ({error.strerror or 'os error'})"
    try:
        try:
            write_bytes(descriptor, text.encode("utf-8"))
        finally:
            os.close(descriptor)
    except OSError as error:
        try:
            os.unlink(path)
        except OSError:
            pass
        return f"could not write {path} ({error.strerror or 'os error'})"
    return None
