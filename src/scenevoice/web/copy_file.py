import os
from pathlib import Path


def copy_file(source: Path, target: Path) -> None:
    """Copy bytes to a NEW `target` (exclusive create, no symlink followed) with the umask-derived mode of an ordinary write."""
    reader = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        writer = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666)
        try:
            while chunk := os.read(reader, 1 << 20):
                view = memoryview(chunk)
                while view:
                    view = view[os.write(writer, view) :]
        finally:
            os.close(writer)
    finally:
        os.close(reader)
