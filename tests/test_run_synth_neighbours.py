import io
import json

from wav_helper import wav_audio

from scenevoice.synth import run_synth

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
