import sys

import pytest
from align_run_helper import Fake, NoTerminal
from line_markers_helper import FIXTURE, SMOKE_LINE_FRAMES, markers, smoke_dir

from scenevoice.cli.main import main


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-key-value")
    monkeypatch.setattr(sys, "stdin", NoTerminal())


def test_align_then_pack_resolve_through_main(tmp_path, capsys):
    plan, out = smoke_dir(tmp_path)
    fake = Fake([FIXTURE.read_bytes(), FIXTURE.read_bytes()])
    assert main(["align", str(plan), str(out)], transcriber_factory=lambda key: fake) == 0
    first = capsys.readouterr()
    assert first.out == "" and "OK 2 scenes, 8 lines, 0 unmatched, 0 from synth record, 2 transcribed" in first.err
    assert main(["pack", "--editor", "resolve", str(plan), str(out)]) == 0
    second = capsys.readouterr()
    assert second.out == "" and "NOTE" not in second.err
    assert second.err.startswith("scenevoice pack: OK 2 scenes")
    assert sorted(p.name for p in out.iterdir()) == [
        "audio",
        "line_timings.json",
        "resolve_timeline.otio",
        "scene_manifest.csv",
    ]
    assert [f for f, _, _ in markers(out)] == sorted(SMOKE_LINE_FRAMES)
