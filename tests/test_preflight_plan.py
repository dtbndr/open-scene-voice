import json

from scenevoice.synth import PlanScene
from scenevoice.synth.preflight_result import PreflightResult
from scenevoice.synth.run_preflight import run_preflight

ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}
ALL = (PlanScene(1, "t", "b1"), PlanScene(2, "t", "b2"), PlanScene(3, "t", "b3"))


def plan_path(tmp_path):
    scenes = [{"ordinal": s.ordinal, "title": s.title, "body": s.body} for s in ALL]
    path = tmp_path / "plan.json"
    path.write_bytes(json.dumps({"scenes": scenes}).encode("utf-8"))
    return path


def test_plan_defaults_to_empty_tuple():
    assert PreflightResult([], {}).plan == ()


def test_full_run_carries_the_whole_plan(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    result = run_preflight(plan_path(tmp_path), None, ENV, tmp_path / "absent.env", out)
    assert isinstance(result, PreflightResult)
    assert result.plan == ALL
    assert result.scenes == list(ALL)


def test_scene_run_carries_the_whole_plan(tmp_path):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    result = run_preflight(plan_path(tmp_path), None, ENV, tmp_path / "absent.env", out, scene=2)
    assert isinstance(result, PreflightResult)
    assert result.scenes == [ALL[1]]
    assert result.total == 3
    assert result.plan == ALL
