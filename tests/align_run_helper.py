"""Shared fixtures for the run_align tests (fake transcribers, pack folders, runner)."""

import io
import json

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
