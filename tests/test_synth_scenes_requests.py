import pytest
from wav_helper import wav_audio

from scenevoice.synth import PlanScene, synth_scenes

GOOD = wav_audio(24)
PLAN = [PlanScene(i, f"t{i}", f"  body {i}\n") for i in (1, 2, 3)]


class Rec:
    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return GOOD


def run(tmp_path, scenes, provider, **kw):
    (tmp_path / "audio").mkdir(exist_ok=True)
    return synth_scenes(scenes, "Say:", "Charon", "en-GB", tmp_path, provider, lambda m: None, **kw)


def test_full_run_requests_carry_neighbours(tmp_path):
    rec = Rec()
    assert run(tmp_path, PLAN, rec, plan=PLAN) is None
    got = [(r.previous_text, r.next_text) for r in rec.requests]
    assert got == [(None, PLAN[1].body), (PLAN[0].body, PLAN[2].body), (PLAN[1].body, None)]
    assert [r.body for r in rec.requests] == [s.body for s in PLAN]
    assert {(r.voice, r.language, r.instruction) for r in rec.requests} == {("Charon", "en-GB", "Say:")}


def test_scene_mode_uses_the_whole_plan_for_neighbours(tmp_path):
    rec = Rec()
    assert run(tmp_path, [PLAN[1]], rec, plan=PLAN, total=3) is None
    assert len(rec.requests) == 1
    assert (rec.requests[0].previous_text, rec.requests[0].next_text) == (PLAN[0].body, PLAN[2].body)


def test_plan_is_required(tmp_path):
    with pytest.raises(TypeError):
        run(tmp_path, PLAN, Rec())
