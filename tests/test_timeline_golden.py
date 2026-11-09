from pathlib import Path

from scenevoice.pack import build_timeline
from scenevoice.synth import PlanScene

FIXTURE = Path(__file__).parent / "fixtures" / "resolve_timeline_two_scenes.otio"


def test_two_scene_timeline_matches_hand_written_golden_bytes():
    scenes = [
        PlanScene(1, "Café, au lait", "First sentence."),
        PlanScene(2, 'The "big" day', "Second sentence."),
    ]
    assert build_timeline(scenes, [50400, 123456])[0] == FIXTURE.read_bytes()
