from pathlib import Path

from .audio_scan import AudioScan
from .has_audio_folder import has_audio_folder
from .hash_wav import hash_wav
from .list_audio_names import list_audio_names
from .regular_file import regular_file


def scan_audio(directory: Path, key_file: Path | None) -> AudioScan:
    """Which synth WAV names `audio/` holds and which of them are voiced (a plain WAV with a readable hash).

    Only exact `NNN.wav` names are considered (`audio_file_name`); a symlink, hard-linked file, directory or the key
    file is named but not voiced. Each plain WAV is hashed once through the no-follow open with the 256 MiB cap.
    """
    names = list_audio_names(directory)
    hashes: dict[int, str] = {}
    for name in names:
        path = regular_file(directory, "audio", name, key_file=key_file)
        digest = hash_wav(path, key_file) if path is not None else None
        if digest is not None:
            hashes[int(name[:-4])] = digest
    return AudioScan(tuple(sorted({int(name[:-4]) for name in names})), hashes, has_audio_folder(directory))
