import hashlib
import io
import json
from pathlib import Path

from wav_helper import make_wav

from scenevoice.align.run_align import run_align

FIXTURE = Path(__file__).parent / "fixtures" / "line_timings_contract_example.json"
ENV = {"OPENROUTER_API_KEY": "dummy-key-value"}

RUN_NOTE = "scenevoice align: NOTE no synth_record.json, all scenes transcribed\n"
NOTE = "scenevoice align: NOTE scene 2 line 2: no match, start_ms null\n"
OK = "scenevoice align: OK 2 scenes, 4 lines, 1 unmatched, 0 from synth record, 2 transcribed\n"

SCENE1 = [
    (" Welcome", 0.23999999865889549),
    (" back.", 0.62),
    (" Today", 1.2344),
    (" we", 1.6),
    (" start.", 1.86),
]
SCENE2 = [
    (" Keep", 0.12),
    (" it", 0.3),
    (" simple.", 0.5),
    (" Sue", 1.9),
    (" you", 2.1),
    (" nexus.", 2.4),
]


class NoTerminal:
    def isatty(self):
        return False

    def read(self):
        raise AssertionError("stdin must not be read")


def body(words):
    return json.dumps(
        {"text": "x", "words": [{"word": w, "start": s, "end": s + 0.1} for w, s in words]}
    ).encode("utf-8")


class Fake:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.received = []

    def __call__(self, wav):
        self.received.append(wav)
        return self.bodies[len(self.received) - 1]


def pack_dir(tmp_path, texts, frames=1000):
    plan = {
        "scenes": [
            {"ordinal": i, "title": f"T{i}", "body": t} for i, t in enumerate(texts, 1)
        ]
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    wavs = []
    for i in range(1, len(texts) + 1):
        data = make_wav(frames + i)
        (out / "audio" / f"{i:03d}.wav").write_bytes(data)
        wavs.append(data)
    return plan_path, out, wavs


def go(plan_path, out, fake, tmp_path):
    err = io.StringIO()
    keys = []

    def factory(key):
        keys.append(key)
        return fake

    code = run_align(
        plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, factory, err
    )
    return code, err.getvalue(), keys


def test_contract_worked_example(tmp_path):
    plan_path, out, wavs = pack_dir(
        tmp_path, ["Welcome back. Today we start.", "Keep it simple. See you next time."]
    )
    fake = Fake([body(SCENE1), body(SCENE2)])
    code, err, keys = go(plan_path, out, fake, tmp_path)
    assert code == 0
    assert err == RUN_NOTE + NOTE + OK
    assert keys == ["dummy-key-value"]
    assert len(fake.received) == 2
    assert fake.received == wavs
    expected = FIXTURE.read_text(encoding="utf-8")
    expected = expected.replace("1" * 64, hashlib.sha256(wavs[0]).hexdigest())
    expected = expected.replace("2" * 64, hashlib.sha256(wavs[1]).hexdigest())
    assert (out / "line_timings.json").read_bytes() == expected.encode("utf-8")
    assert sorted(p.name for p in out.iterdir()) == ["audio", "line_timings.json"]


def test_zero_note_success(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Welcome back. Today we start."])
    code, err, _ = go(plan_path, out, Fake([body(SCENE1)]), tmp_path)
    assert code == 0
    assert err == (
        RUN_NOTE + "scenevoice align: OK 1 scenes, 2 lines, 0 unmatched, 0 from synth record, 1 transcribed\n"
    )


def test_last_zero_token_sentence_is_unmatched(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Welcome back. ..."])
    code, err, _ = go(plan_path, out, Fake([body(SCENE1[:2])]), tmp_path)
    assert code == 0
    assert err == (
        RUN_NOTE
        + "scenevoice align: NOTE scene 1 line 2: no match, start_ms null\n"
        "scenevoice align: OK 1 scenes, 2 lines, 1 unmatched, 0 from synth record, 1 transcribed\n"
    )
    data = json.loads((out / "line_timings.json").read_text())
    assert data["scenes"][0]["lines"][1] == {"text": "...", "start_ms": None}


def test_notes_come_after_all_calls_in_scene_order(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Zebra yak.", "Welcome back. Quartz."])
    log = []

    class Spy:
        def __init__(self):
            self.n = 0

        def __call__(self, wav):
            self.n += 1
            log.append(("call", self.n))
            return body(SCENE1[:2]) if self.n == 2 else body([(" nope", 0.1)])

    class Err(io.StringIO):
        def write(self, text):
            log.append(("write", text))
            return super().write(text)

    err = Err()
    code = run_align(plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, lambda k: Spy(), err)
    assert code == 0
    assert log[0] == ("call", 1) and log[1] == ("call", 2)
    writes = [text for kind, text in log if kind == "write"]
    assert writes == [
        RUN_NOTE,
        "scenevoice align: NOTE scene 1 line 1: no match, start_ms null\n",
        "scenevoice align: NOTE scene 2 line 2: no match, start_ms null\n",
        "scenevoice align: OK 2 scenes, 3 lines, 2 unmatched, 0 from synth record, 2 transcribed\n",
    ]


def test_hash_comes_from_the_held_bytes_not_the_file_at_write_time(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, ["Welcome back."])

    def transcriber(wav):
        (out / "audio" / "001.wav").write_bytes(make_wav(5000))
        return body(SCENE1[:2])

    run_align(
        plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, lambda k: transcriber, io.StringIO()
    )
    data = json.loads((out / "line_timings.json").read_text())
    assert data["scenes"][0]["sha256"] == hashlib.sha256(wavs[0]).hexdigest()


def test_short_wav_is_refused_by_the_zero_frame_rule(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Welcome back."], frames=0)
    (out / "audio" / "001.wav").write_bytes(make_wav(999))
    fake = Fake([body(SCENE1[:2])])
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 1
    assert err.startswith("scenevoice align: FAIL scene 1: audio/001.wav")
    assert fake.received == []
