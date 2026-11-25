import os
from pathlib import Path

from .beats_light_check import beats_light_check
from .beats_messages import BEATS_UNREADABLE, COULD_NOT_FINISH
from .job_availability import BEATS_EXIST
from .read_beats_state import BEATS_CAP
from .read_json_file import read_json_file


def swap_beats(directory: Path, candidate: Path, revision: str, redo: bool, key_file: Path | None) -> str | None:
    """Put a finished candidate in place as `beats.json` (J9), or return the failure message and change nothing.

    The candidate is read bounded and without following a link, must pass the light shape check and name the SHA-256
    of the script bytes that were counted (`revision`), else the old beats stay. A redo `os.replace`s the old file;
    a first run links the candidate to `beats.json`, so a `beats.json` made meanwhile (a dangling symlink included) is
    never overwritten and the job fails. The caller removes the candidate afterwards (after a link it is the second name).
    """
    read = read_json_file(directory, candidate.name, BEATS_CAP, key_file)
    if read.state != "ok" or beats_light_check(read.value) != revision:
        return BEATS_UNREADABLE
    target = directory / "beats.json"
    try:
        if redo:
            os.replace(candidate, target)
        else:
            os.link(candidate, target, follow_symlinks=False)
    except FileExistsError:
        return BEATS_EXIST
    except OSError:
        return COULD_NOT_FINISH
    return None
