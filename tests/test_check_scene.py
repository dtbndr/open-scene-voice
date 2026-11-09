import pytest

from scenevoice.synth.check_scene import check_scene
from scenevoice.validation import Violation


@pytest.mark.parametrize("scene,count", [(1, 5), (5, 5), (3, 5), (1, 1)])
def test_in_range_scene_passes(scene, count):
    assert check_scene(scene, count) is None


@pytest.mark.parametrize("scene", [0, -3, 6])
def test_out_of_range_scene_is_refused_naming_scene_count(scene):
    violation = check_scene(scene, 5)
    assert isinstance(violation, Violation)
    assert violation.rule == "scene"
    assert violation.message == f"--scene {scene} is out of range (the plan has 5 scenes)"


def test_one_scene_plan_uses_plural_form():
    violation = check_scene(2, 1)
    assert violation is not None
    assert violation.message == "--scene 2 is out of range (the plan has 1 scenes)"
