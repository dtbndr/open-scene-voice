"""Shared pieces for the line-marker pack tests (probe script, fixture transcriber, marker reader)."""

import hashlib
import io
import json
from pathlib import Path

from align_run_helper import Fake, go
from pack_run_helper import FakeStdin, put_wav, scene, write_plan

from scenevoice.pack import run_pack

PROBE = (
    "Rome was burning, but one man refused to panic. In the winter of 169 AD, Emperor Marcus "
    "Aurelius faced plague, war and betrayal all at once. Most rulers would have crumbled. "
    "Marcus opened a notebook instead."
)
FIXTURE = Path(__file__).parent / "fixtures" / "openrouter" / "whisper_verbose_json.json"
SMOKE_FRAMES = 408000
SMOKE_LINE_FRAMES = [0, 6, 110, 297, 345, 418, 424, 528, 715, 763]


def smoke_dir(tmp_path, name="w"):
    """Two probe-script scenes with 17 s WAVs; returns (plan, out)."""
    root = tmp_path / name
    root.mkdir()
    out = root / "out"
    out.mkdir()
    for n in (1, 2):
        put_wav(out, n, SMOKE_FRAMES)
    plan = write_plan(root, [scene(1, "One", PROBE), scene(2, "Two", PROBE)])
    return plan, out


def align(plan, out, tmp_path):
    fake = Fake([FIXTURE.read_bytes(), FIXTURE.read_bytes()])
    code, text, _ = go(plan, out, fake, tmp_path)
    assert code == 0 and "OK 2 scenes, 8 lines, 0 unmatched, 0 from synth record, 2 transcribed" in text


def pack(plan, out):
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), out, err, "resolve")
    return code, err.getvalue()


def markers(out):
    stack = json.loads((out / "resolve_timeline.otio").read_text())["tracks"]
    return [(m["marked_range"]["start_time"]["value"], m["color"], m["name"]) for m in stack["markers"]]


def sha(out, ordinal):
    return hashlib.sha256((out / "audio" / f"{ordinal:03d}.wav").read_bytes()).hexdigest()


def write_timings(out, entries):
    """entries: (ordinal, sha256, [start_ms, ...]) tuples."""
    scenes = [
        {"ordinal": n, "sha256": h, "lines": [{"text": f"S{n} line {i}.", "start_ms": ms} for i, ms in enumerate(starts, 1)]}
        for n, h, starts in entries
    ]
    (out / "line_timings.json").write_bytes(json.dumps({"scenes": scenes}).encode())
