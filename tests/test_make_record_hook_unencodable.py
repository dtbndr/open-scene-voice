"""D21: an alignment character that cannot be encoded as UTF-8 is a record-write failure, not a traceback."""

import json
import wave
from pathlib import Path

import pytest
from wav_helper import make_wav

from scenevoice.cli.main import main
from scenevoice.synth import (
    Alignment,
    ProviderAudio,
    RecordSettings,
    make_elevenlabs_provider,
)
from scenevoice.synth.make_record_hook import make_record_hook

FIXTURES = Path(__file__).parent / "fixtures" / "elevenlabs"
FAILURE = "could not write synth_record.json"
SETTINGS = RecordSettings("EXAVITQu4vr4xnSDxMaL", "eleven_flash_v2_5", None, None)
GOOD = Alignment(("a", "b"), (0.0, 0.08), (0.08, 0.16))
LONE = Alignment(("\ud83d", "t"), (0.0, 0.1), (0.1, 0.2))


def test_hook_returns_the_failure_text_and_keeps_the_record(tmp_path):
    hook = make_record_hook(tmp_path, SETTINGS, [])
    assert hook(1, ProviderAudio("audio/wav", make_wav(5), GOOD)) is None
    before = (tmp_path / "synth_record.json").read_bytes()
    assert hook(2, ProviderAudio("audio/wav", make_wav(5), LONE)) == FAILURE
    assert (tmp_path / "synth_record.json").read_bytes() == before


def test_full_run_stops_with_the_write_failure_and_no_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "dummy-eleven-key")
    plan = {"scenes": [{"ordinal": i, "title": "t", "body": f"Body {i}."} for i in (1, 2, 3)]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    names = {2: "lone_surrogate_character.json"}
    calls = []

    def post(url, headers, body, timeout):
        calls.append(url)
        return (FIXTURES / names.get(len(calls), "success_flash.json")).read_bytes()

    out = tmp_path / "out"
    code = main(
        ["synth", "plan.json", "--out", str(out), "--voice", "EXAVITQu4vr4xnSDxMaL",
         "--model", "eleven_flash_v2_5"],
        provider_factory=lambda env, m: make_elevenlabs_provider(env, m, post=post))
    captured = capsys.readouterr()
    assert code == 1 and captured.out == ""
    assert f"scenevoice synth: FAIL scene 2: {FAILURE}" in captured.err
    assert "Traceback" not in captured.err
    for n in (1, 2):
        with wave.open(str(out / "audio" / f"00{n}.wav")) as w:
            assert w.getnframes() == 4800
    assert not (out / "audio" / "003.wav").exists()
    scenes = json.loads((out / "synth_record.json").read_text(encoding="utf-8"))["scenes"]
    assert [s["ordinal"] for s in scenes] == [1]
    assert len(calls) == 2


@pytest.mark.parametrize("alignment", [LONE])
def test_positive_control_the_lone_surrogate_really_cannot_be_encoded(alignment):
    with pytest.raises(UnicodeEncodeError):
        "".join(alignment.characters).encode("utf-8")
