import io
import json

import pytest
from wav_helper import wav_audio

from scenevoice.synth import PlanScene, neighbour_texts, run_synth
from scenevoice.synth.check_scene_target import check_scene_target
from scenevoice.validation import Violation


@pytest.fixture(autouse=True)
def _audio_dir(tmp_path):
    (tmp_path / "audio").mkdir()


def test_scene_target_absent_target_passes(tmp_path):
    assert check_scene_target(tmp_path, 4) is None


def test_scene_target_flat_file_or_directory_beside_audio_is_ignored(tmp_path):
    (tmp_path / "004.wav").mkdir()
    assert check_scene_target(tmp_path, 4) is None


def test_scene_target_directory_target_is_refused(tmp_path):
    (tmp_path / "audio" / "004.wav").mkdir()
    violation = check_scene_target(tmp_path, 4)
    assert isinstance(violation, Violation)
    assert violation.rule == "scene-target"
    assert violation.message == "004.wav exists and is not a regular file"


def test_scene_target_symlink_to_regular_file_is_refused(tmp_path):
    real = tmp_path / "audio" / "real.wav"
    real.write_bytes(b"x")
    (tmp_path / "audio" / "004.wav").symlink_to(real)
    violation = check_scene_target(tmp_path, 4)
    assert violation is not None
    assert violation.message == "004.wav exists and is not a regular file"


def test_scene_target_dangling_symlink_is_refused(tmp_path):
    (tmp_path / "audio" / "004.wav").symlink_to(tmp_path / "audio" / "nowhere")
    violation = check_scene_target(tmp_path, 4)
    assert violation is not None
    assert violation.message == "004.wav exists and is not a regular file"


THREE = [PlanScene(1, "a", "body one"), PlanScene(2, "b", "body two"), PlanScene(3, "c", "body three")]


def test_first_scene_has_no_previous():
    assert neighbour_texts(THREE, 1) == (None, "body two")


def test_middle_scene_has_both_neighbours():
    assert neighbour_texts(THREE, 2) == ("body one", "body three")


def test_last_scene_has_no_next():
    assert neighbour_texts(THREE, 3) == ("body two", None)


def test_bodies_are_verbatim():
    plan = [PlanScene(1, "a", "  lead\n"), PlanScene(2, "b", "mid"), PlanScene(3, "c", "\ttrail  ")]
    assert neighbour_texts(plan, 2) == ("  lead\n", "\ttrail  ")


ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "SeCrEt-key-0123456789",
}


BODIES = {1: "first body", 2: "second body", 3: "third body"}


class Rec:
    def __init__(self):
        self.requests = []

    def factory(self, env, model):
        def provider(request):
            self.requests.append(request)
            return wav_audio(frames=20)

        return provider


def run(tmp_path, rec, scene):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"scenes": [
        {"ordinal": i, "title": "t", "body": b} for i, b in BODIES.items()]}))
    stderr = io.StringIO()
    code = run_synth(path, None, ENV, tmp_path / "missing.env", tmp_path / "out", "Callirrhoe",
                     "gemini-3.8-flash-tts", "en-GB", None, rec.factory, stderr, scene=scene)
    assert code == 0, stderr.getvalue()


def test_scene_three_gets_previous_body_and_no_next(tmp_path):
    full = Rec()
    run(tmp_path, full, None)
    assert [(r.previous_text, r.next_text) for r in full.requests] == [
        (None, "second body"), ("first body", "third body"), ("second body", None)]
    regen = Rec()
    run(tmp_path, regen, 3)
    assert len(regen.requests) == 1
    assert regen.requests[0].previous_text == "second body"
    assert regen.requests[0].next_text is None
