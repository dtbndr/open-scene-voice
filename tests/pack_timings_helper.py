import hashlib
import io
import json

from pack_run_helper import FakeStdin, put_wav, scene, write_plan

from scenevoice.pack import run_pack

SCENES = [scene(1, "One"), scene(2, "Two")]
MISSING = "scenevoice pack: NOTE no line_timings.json, scene markers only\n"


def make_out(tmp_path, name="out", frames=(24000, 12000)):
    out = tmp_path / name
    out.mkdir()
    for n, f in enumerate(frames, 1):
        put_wav(out, n, f)
    return out


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


def run(tmp_path, out, editor="resolve"):
    err = io.StringIO()
    code = run_pack(write_plan(tmp_path, SCENES), FakeStdin(b""), out, err, editor)
    return code, err.getvalue()


def snapshot(out):
    return sorted(str(p.relative_to(out)) for p in out.rglob("*"))
