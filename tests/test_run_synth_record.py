import hashlib
import io
import json
import os
import sys

import pytest
from wav_helper import make_wav

from scenevoice.synth import ProviderAudio, ProviderError, run_synth

KEY = "SeCrEt-key-0123456789"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": KEY,
}
PREFIX = "scenevoice synth: "
MESSAGE = "could not write synth_record.json"


class Stdin:
    def isatty(self):
        return True


def write_plan(tmp_path, n=3):
    path = tmp_path / "plan.json"
    scenes = [{"ordinal": i, "title": "t", "body": f"body {i}"} for i in range(1, n + 1)]
    path.write_text(json.dumps({"scenes": scenes}))
    return path


class Rec:
    def __init__(self, fail_on=None, on_factory=None):
        self.calls = 0
        self.factories = 0
        self.fail_on = fail_on
        self.on_factory = on_factory

    def factory(self, env, model):
        self.factories += 1
        if self.on_factory is not None:
            self.on_factory()

        def provider(request):
            self.calls += 1
            if self.calls == self.fail_on:
                raise ProviderError("boom")
            return ProviderAudio("audio/wav", make_wav(10 + self.calls))

        return provider


def run(tmp_path, rec, instruction=None, **kw):
    err = io.StringIO()
    args = dict(
        plan_path=write_plan(tmp_path),
        stdin=Stdin(),
        process_env=ENV,
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice="Callirrhoe",
        model="gemini-3.8-flash-tts",
        language="en-GB",
        instruction=instruction,
        provider_factory=rec.factory,
        stderr=err,
    )
    args.update(kw)
    return run_synth(**args), err.getvalue()


def record(tmp_path):
    return json.loads((tmp_path / "out" / "synth_record.json").read_text())["scenes"]


def test_full_run_writes_one_entry_per_scene(tmp_path, capsys):
    code, err = run(tmp_path, Rec())
    assert code == 0
    scenes = record(tmp_path)
    assert [s["ordinal"] for s in scenes] == [1, 2, 3]
    for s in scenes:
        wav = (tmp_path / "out" / "audio" / f"{s['ordinal']:03d}.wav").read_bytes()
        assert s["sha256"] == hashlib.sha256(wav).hexdigest()
        assert (s["voice"], s["model"], s["language"], s["instruction"], s["alignment"]) == (
            "Callirrhoe", "gemini-3.8-flash-tts", "en-GB", None, None)
    assert capsys.readouterr().out == ""


def test_instruction_recorded_verbatim(tmp_path, capsys):
    code, _ = run(tmp_path, Rec(), instruction="Say warmly:")
    assert code == 0
    assert {s["instruction"] for s in record(tmp_path)} == {"Say warmly:"}
    assert capsys.readouterr().out == ""


def test_empty_record_exists_before_factory(tmp_path, capsys):
    seen = []

    def inspect():
        path = tmp_path / "out" / "synth_record.json"
        seen.append(path.read_bytes() if path.exists() else None)

    code, _ = run(tmp_path, Rec(on_factory=inspect))
    assert code == 0
    assert seen == [b'{\n  "scenes": []\n}\n']
    assert capsys.readouterr().out == ""


def test_provider_failure_on_scene_two_keeps_entry_one(tmp_path, capsys):
    code, err = run(tmp_path, Rec(fail_on=2))
    assert code == 1 and "scene 2: boom" in err
    assert [s["ordinal"] for s in record(tmp_path)] == [1]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("content", [b"{not json", b"\xff\xfe", b'{"scenes": []}\n'])
def test_existing_regular_record_replaced_without_reading(tmp_path, content, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "synth_record.json").write_bytes(content)
    code, _ = run(tmp_path, Rec())
    assert code == 0 and len(record(tmp_path)) == 3
    assert capsys.readouterr().out == ""


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores modes")
def test_mode_000_record_replaced(tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    target = out / "synth_record.json"
    target.write_bytes(b"old")
    target.chmod(0)
    try:
        code, _ = run(tmp_path, Rec())
        assert code == 0 and len(record(tmp_path)) == 3
    finally:
        if target.exists():
            target.chmod(0o644)
    assert capsys.readouterr().out == ""


def test_refused_runs_leave_existing_record_byte_identical(tmp_path, capsys):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / "synth_record.json").write_bytes(b"old bytes")
    (out / "audio" / "002.wav").write_bytes(b"x")
    rec = Rec()
    code, err = run(tmp_path, rec)  # collision
    assert code == 1 and "output already exists" in err
    code, err = run(tmp_path, rec, plan_path=tmp_path / "missing-plan.json")  # plan error
    assert code == 1
    assert rec.factories == 0
    assert (out / "synth_record.json").read_bytes() == b"old bytes"
    assert capsys.readouterr().out == ""


def test_non_regular_record_refused_and_left_alone(tmp_path, capsys):
    out = tmp_path / "out"
    (out / "synth_record.json").mkdir(parents=True)
    rec = Rec()
    code, err = run(tmp_path, rec)
    assert code == 1 and PREFIX + "FAIL synth_record.json exists and is not a regular file" in err
    assert (out / "synth_record.json").is_dir() and rec.factories == 0
    assert not (out / "audio").exists()
    assert capsys.readouterr().out == ""


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores modes")
def test_unwritable_dir_fails_empty_write_before_factory(tmp_path, capsys):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    out.chmod(0o555)
    rec = Rec()
    try:
        code, err = run(tmp_path, rec)
    finally:
        out.chmod(0o755)
    assert code == 1
    assert err == PREFIX + "FAIL " + MESSAGE + "\n"
    assert rec.factories == 0 and rec.calls == 0
    assert capsys.readouterr().out == ""


def test_injected_empty_write_failure_before_factory(tmp_path, monkeypatch, capsys):
    calls = []

    def fake(directory, data):
        calls.append(data)
        return MESSAGE

    monkeypatch.setattr(sys.modules["scenevoice.synth.run_synth"], "write_record_file", fake)
    rec = Rec()
    code, err = run(tmp_path, rec)
    assert calls == [b'{\n  "scenes": []\n}\n']  # positive control
    assert code == 1 and err == PREFIX + "FAIL " + MESSAGE + "\n"
    assert rec.factories == 0
    assert capsys.readouterr().out == ""


def test_record_write_failure_after_scene_one(tmp_path, monkeypatch, capsys):
    calls = []

    def fake(directory, data):
        calls.append(data)
        return MESSAGE

    monkeypatch.setattr(sys.modules["scenevoice.synth.make_record_hook"], "write_record_file", fake)
    rec = Rec()
    code, err = run(tmp_path, rec)
    assert len(calls) == 1  # positive control: the hook's write was reached
    assert code == 1 and err == PREFIX + "FAIL scene 1: " + MESSAGE + "\n"
    assert rec.calls == 1
    assert sorted(p.name for p in (tmp_path / "out" / "audio").iterdir()) == ["001.wav"]
    assert capsys.readouterr().out == ""
