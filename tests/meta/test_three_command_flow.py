import csv
import json

import pytest
from wav_helper import wav_audio

from scenevoice.cli.main import main
from scenevoice.synth import ENV_NAMES

SCRIPT = "# Two scenes\n\n## Opening\nHello there.\n\n## Closing\nGoodbye now.\n"
AUDIO = wav_audio(24000)  # one second of silence


class FakeProvider:
    def __init__(self):
        self.calls = []

    def factory(self, env, model):
        def provider(request):
            body = request.body
            self.calls.append(body)
            return AUDIO

        return provider


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ENV_NAMES:
        monkeypatch.setenv(name, "dummy-value")
    return tmp_path


def test_plan_synth_pack_run_end_to_end_on_the_audio_layout(env, capsys):
    plan_file = env / "plan.json"  # outside DIR, as the README shows
    out = env / "out"

    script = env / "script.md"
    script.write_text(SCRIPT, encoding="utf-8")
    assert main(["plan", str(script)]) == 0
    plan_stdout = capsys.readouterr().out
    plan_file.write_text(plan_stdout, encoding="utf-8")
    assert len(json.loads(plan_stdout)["scenes"]) == 2

    fake = FakeProvider()
    synth = ["synth", str(plan_file), "--out", str(out), "--voice", "Charon",
             "--model", "gemini-3.8-flash-tts"]
    assert main(synth, provider_factory=fake.factory) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(fake.calls) == 2

    assert main(["pack", str(plan_file), str(out)]) == 0
    assert capsys.readouterr().out == ""

    assert (out / "audio" / "001.wav").is_file()
    assert (out / "audio" / "002.wav").is_file()
    assert sorted(p.name for p in out.iterdir()) == ["audio", "scene_manifest.csv", "synth_record.json"]
    with (out / "scene_manifest.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["file"] for row in rows] == ["audio/001.wav", "audio/002.wav"]
