import os
import tempfile
from pathlib import Path

from scenevoice.synth.wav_name import wav_name
from scenevoice.validation import Violation

_RULE = "out-dir"


def _current_umask() -> int:
    mask = os.umask(0)
    try:
        return mask
    finally:
        os.umask(mask)


def write_wav(out_dir: str | Path, ordinal: int, wav: bytes) -> Violation | None:
    """Write the given WAV bytes unchanged as NNN.wav via a same-directory temp file (never ending .wav), then atomic rename.

    The file gets the normal umask-derived mode before the rename, not mkstemp's 0600.
    """
    temp = None
    try:
        fd, temp = tempfile.mkstemp(prefix=".write-", suffix=".tmp", dir=out_dir)
        with os.fdopen(fd, "wb") as f:
            f.write(wav)
        os.chmod(temp, 0o666 & ~_current_umask())
        os.replace(temp, os.path.join(out_dir, wav_name(ordinal)))
        return None
    except OSError:
        if temp is not None:
            try:
                os.remove(temp)
            except OSError:
                pass
        return Violation(_RULE, f"could not write {wav_name(ordinal)}")
