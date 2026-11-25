"""A project folder holding a full old generation (WAVs, record, line markers, pack) for the Start again tests."""

from pathlib import Path

FIXED = ("synth_record.json", "line_timings.json", "scene_manifest.csv", "resolve_timeline.otio")
WAV_NAMES = ("001.wav", "002.wav")


def old_generation(directory: Path) -> dict[str, bytes]:
    """Write every allowlisted file plus bystanders; returns the allowlisted ones (relative name to bytes)."""
    (directory / "audio").mkdir(parents=True, exist_ok=True)
    files = {name: f"old {name}".encode() for name in FIXED}
    files.update({f"audio/{name}": f"old wav {name}".encode() for name in WAV_NAMES})
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return files


BYSTANDERS = ("script.md", "beats.json", ".write-beats-aa.tmp", "audio/.write-001.wav.tmp", "audio/001.wav.bak", "audio/1.wav", "notes.txt")


def bystanders(directory: Path) -> dict[str, bytes]:
    found = {}
    for name in BYSTANDERS:
        (directory / name).write_bytes(f"keep {name}".encode())
        found[name] = f"keep {name}".encode()
    return found


def snapshot(directory: Path) -> dict[str, bytes]:
    """Every regular file under `directory` (relative name to bytes), for before and after comparisons."""
    return {str(p.relative_to(directory)): p.read_bytes() for p in sorted(directory.rglob("*")) if p.is_file() and not p.is_symlink()}
