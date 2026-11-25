"""Shared fixtures for the run_align tests (fake transcribers, pack folders, runner)."""

import io
import json

from record_helper import eleven_entry, write_record
from wav_helper import make_wav

from scenevoice.align import TranscriptionError
from scenevoice.align.run_align import run_align

KEY = "dummy-key-value"
ENV = {"OPENROUTER_API_KEY": KEY}
PREFIX = "scenevoice align: "
HELLO = [(" Hello", 0.1), (" there.", 0.5)]


class NoTerminal:
    def isatty(self):
        return False

    def read(self):
        raise AssertionError("stdin must not be read")


def body(words):
    return json.dumps(
        {"text": "x", "words": [{"word": w, "start": s, "end": s + 0.1} for w, s in words]}
    ).encode("utf-8")


class Fake:
    """Counts calls and records the bytes; items may be bodies or exceptions."""

    def __init__(self, items):
        self.items = list(items)
        self.received = []

    def __call__(self, wav):
        self.received.append(wav)
        item = self.items[len(self.received) - 1]
        if isinstance(item, Exception):
            raise item
        return item


def fail_with(status, text=""):
    return TranscriptionError(status, text)


def pack_dir(tmp_path, texts, frames=1000, make_wavs=True):
    plan = {"scenes": [{"ordinal": i, "title": f"T{i}", "body": t} for i, t in enumerate(texts, 1)]}
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    wavs = []
    for i in range(1, len(texts) + 1):
        data = make_wav(frames + i)
        if make_wavs:
            (out / "audio" / f"{i:03d}.wav").write_bytes(data)
        wavs.append(data)
    return plan_path, out, wavs


def go(plan_path, out, fake, tmp_path, env=None, stdin=None, dotenv=None):
    """Run run_align; returns (code, stderr text, keys passed to the factory)."""
    err = io.StringIO()
    keys = []

    def factory(key):
        keys.append(key)
        return fake

    code = run_align(
        plan_path,
        NoTerminal() if stdin is None else stdin,
        ENV if env is None else env,
        tmp_path / "no.env" if dotenv is None else dotenv,
        out,
        factory,
        err,
    )
    text = err.getvalue()
    assert KEY not in text
    return code, text, keys


# Record-routing fixtures shared by the run_align record and notes tests.
BODIES = ["Welcome back. Today we start.", "Keep it simple. See you next time."]
RUN_NOTE = PREFIX + "NOTE no synth_record.json, all scenes transcribed\n"
SCENE2_NOTE = PREFIX + "NOTE scene 2 line 2: no match, start_ms null\n"
F_NOTE = PREFIX + "NOTE scene 2: alignment text differs from plan body, transcribed\n"
SCENE1 = [
    (" Welcome", 0.23999999865889549),
    (" back.", 0.62),
    (" Today", 1.2344),
    (" we", 1.6),
    (" start.", 1.86),
]
SCENE2 = [
    (" Keep", 0.12),
    (" it", 0.3),
    (" simple.", 0.5),
    (" Sue", 1.9),
    (" you", 2.1),
    (" nexus.", 2.4),
]
SCENE2_FULL = [
    (" Keep", 0.12),
    (" it", 0.3),
    (" simple.", 0.5),
    (" See", 1.5),
    (" you", 1.6),
    (" next", 1.7),
    (" time.", 1.8),
]


def alignment_at(text, starts_at):
    """Alignment of one element per character; the start is the latest override at or before it."""
    starts, current = [], 0.0
    for i in range(len(text)):
        current = starts_at.get(i, current)
        starts.append(current)
    return {
        "characters": list(text),
        "character_start_times_seconds": starts,
        "character_end_times_seconds": [s + 0.01 for s in starts],
    }


def record_entries(wavs, texts, starts):
    return [
        eleven_entry(n, wav, text, alignment=alignment_at(text, at))
        for n, (wav, text, at) in enumerate(zip(wavs, texts, starts, strict=True), 1)
    ]


def worked_record(out, wavs):
    starts = [{0: 0.24, 14: 1.2344}, {0: 0.12, 16: 1.5}]
    return write_record(out, *record_entries(wavs, BODIES, starts))


def fail_if_called(key):
    raise AssertionError("the factory must not be called")
