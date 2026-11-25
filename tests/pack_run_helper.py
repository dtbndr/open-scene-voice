import hashlib
import io
import json
from collections.abc import Sequence

from wav_helper import make_wav

from scenevoice.pack import run_pack

MISSING_NOTE = "scenevoice pack: NOTE no line_timings.json, scene markers only\n"


def plan_bytes(scenes: Sequence[dict]) -> bytes:
    return json.dumps({"scenes": scenes}).encode("utf-8")


def scene(i: int, title: str = "T", body: str = "Hello.") -> dict:
    return {"ordinal": i, "title": title, "body": body}


SCENES = [scene(1, "One"), scene(2, "Two")]


def write_plan(tmp_path, scenes: Sequence[dict] = tuple(SCENES)):
    path = tmp_path / "plan.json"
    path.write_bytes(plan_bytes(scenes))
    return path


def put_wav(directory, ordinal: int, frames: int = 24000) -> None:
    (directory / "audio").mkdir(exist_ok=True)
    (directory / "audio" / f"{ordinal:03d}.wav").write_bytes(make_wav(frames))


def make_out(tmp_path, name="out", frames=(24000, 12000)):
    """A fresh pack directory holding one valid WAV per entry of frames."""
    out = tmp_path / name
    out.mkdir()
    for n, f in enumerate(frames, 1):
        put_wav(out, n, f)
    return out


class FakeStdin:
    def __init__(self, data: bytes, tty: bool = False):
        self.buffer = io.BytesIO(data)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def run_text(plan, out, editor=None):
    """Run run_pack on a plan path (or None); returns (exit code, stderr text)."""
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), out, err, editor)
    return code, err.getvalue()


def run(tmp_path, out, editor="resolve"):
    """An editor run of the two-scene plan."""
    return run_text(write_plan(tmp_path), out, editor)


def ok_line(out, count=2):
    return (
        f"scenevoice pack: OK {count} scenes written to {out}/scene_manifest.csv"
        f" and {out}/resolve_timeline.otio\n"
    )


def wav_hash(out, ordinal):
    return hashlib.sha256((out / "audio" / f"{ordinal:03d}.wav").read_bytes()).hexdigest()


def timings_doc(entries: list[tuple[int, str]]) -> bytes:
    scenes = [
        {"ordinal": n, "sha256": h, "lines": [{"text": "Hello.", "start_ms": 0}]} for n, h in entries
    ]
    return json.dumps({"scenes": scenes}).encode()


def snapshot(out):
    return sorted(str(p.relative_to(out)) for p in out.rglob("*"))
