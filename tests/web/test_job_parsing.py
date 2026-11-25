import hashlib
import json

import pytest
from detail_helper import sha
from job_events_helper import status_of
from record_helper import eleven_entry, gemini_entry, write_record

from scenevoice.align.route_record import route_record
from scenevoice.synth import PlanScene, SceneWav
from scenevoice.web import (
    FIXED_FAILURE,
    AudioScan,
    JobRequest,
    JobStatus,
    PlannedScene,
    ProjectFacts,
    current_job_json,
    job_echo,
    listen_scenes,
    parse_job_request,
    read_record,
    snapshot_event,
)
from scenevoice.web.job_scenes import job_scenes
from scenevoice.web.plan_scene_count import plan_scene_count
from scenevoice.web.record_read import RecordRead
from scenevoice.web.timings_read import TimingsRead

REV = "a" * 64
CONFIRM = {"scenes": 2, "characters": 30, "model": "m", "revision": REV}
SYNTH = {"kind": "synth", "mode": "all", "voice": "V", "model": "m", "confirm": CONFIRM}


def parsed(**changes):
    body = {**SYNTH, **changes}
    return parse_job_request({key: value for key, value in body.items() if value is not ...})


def test_a_synth_all_request_with_every_field_is_read_whole():
    request = parsed(language="en-GB", instruction="Calm")
    assert request == JobRequest("synth", "all", None, "V", "m", "en-GB", "Calm", CONFIRM)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"kind": "synth", "mode": "rest", "confirm": CONFIRM}, JobRequest("synth", "rest", confirm=CONFIRM)),
        ({"kind": "synth-scene", "scene": 3, "confirm": CONFIRM}, JobRequest("synth-scene", scene=3, confirm=CONFIRM)),
        ({"kind": "beats", "model": "x/y", "confirm": CONFIRM}, JobRequest("beats", model="x/y", confirm=CONFIRM)),
        ({"kind": "beats-redo", "model": "x/y", "confirm": CONFIRM}, JobRequest("beats-redo", model="x/y", confirm=CONFIRM)),
        ({"kind": "align", "confirm": {"scenes": 0, "revision": REV}}, JobRequest("align", confirm={"scenes": 0, "revision": REV})),
        ({"kind": "pack"}, JobRequest("pack")),
    ],
)
def test_each_kind_reads_with_only_its_own_fields(body, expected):
    assert parse_job_request(body) == expected


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "play"},
        {**SYNTH, "mode": "most"},
        {"kind": "synth", "mode": "all", "model": "m", "confirm": CONFIRM},  # all needs a voice
        {**SYNTH, "extra": 1},
        {"kind": "synth-scene", "scene": 0, "confirm": CONFIRM},
        {"kind": "pack", "confirm": CONFIRM},  # a free kind takes no confirm
    ],
)
def test_a_body_with_a_wrong_shape_is_refused(body):
    assert parse_job_request(body) is None


@pytest.mark.parametrize("value", ["", "x" * 1001, "a\x00b", 3])
def test_a_text_field_must_be_one_to_one_thousand_characters_without_nul(value):
    assert parsed(voice=value) is None


# Paid call without confirm: every refused confirm shape below starts no paid child.
@pytest.mark.parametrize(
    "confirm",
    [
        ...,
        {**CONFIRM, "extra": 1},
        {key: value for key, value in CONFIRM.items() if key != "revision"},
        {**CONFIRM, "scenes": "2"},
        {**CONFIRM, "characters": 1.5},
        {**CONFIRM, "model": 3},
        {**CONFIRM, "revision": "A" * 64},
        {**CONFIRM, "revision": "a" * 63},
    ],
)
def test_a_paid_kind_needs_a_whole_confirm_with_a_lowercase_hex_revision(confirm):
    assert parsed(confirm=confirm) is None


SCENES = (PlannedScene(1, "A long title that is never counted", "Café one."), PlannedScene(2, "T", "\U0001f600 two"))


def test_characters_are_code_points_of_the_bodies_only_and_the_revision_hashes_the_bytes():
    data = b"# A\nsome bytes"
    assert job_echo(SCENES, "m", data) == {
        "scenes": 2,
        "characters": len("Café one.") + len("\U0001f600 two"),
        "model": "m",
        "revision": hashlib.sha256(data).hexdigest(),
    }


def test_one_scene_counts_only_its_own_body():
    echo = job_echo(SCENES[1:], "m", b"x")
    assert (echo["scenes"], echo["characters"]) == (1, 5)


def test_a_multi_byte_body_counts_by_code_point_not_by_byte():
    assert job_echo((PlannedScene(1, "t", "ééé"),), "m", b"x")["characters"] == 3


def test_a_same_length_one_letter_change_gives_a_different_revision():
    assert job_echo(SCENES, "m", b"abc")["revision"] != job_echo(SCENES, "m", b"abd")["revision"]


def test_the_model_is_carried_as_given():
    assert job_echo(SCENES, "eleven_flash_v2_5", b"x")["model"] == "eleven_flash_v2_5"


SCENES_job_scenes = tuple(PlannedScene(n, f"Scene {n}", f"body {n}") for n in (1, 2, 3, 4))


def facts(voiced: tuple[int, ...]) -> ProjectFacts:
    audio = AudioScan(named=voiced, hashes={n: sha(b"x") for n in voiced})
    return ProjectFacts("ok", SCENES_job_scenes, audio, RecordRead("none", ()), TimingsRead("none", ()), "none")


def names(request: JobRequest, voiced: tuple[int, ...] = ()) -> list[int]:
    return [scene.ordinal for scene in job_scenes(request, SCENES_job_scenes, facts(voiced))]


def test_all_and_start_again_voice_every_scene_even_when_some_are_voiced():
    assert names(JobRequest("synth", "all")) == [1, 2, 3, 4]
    assert names(JobRequest("synth", "restart"), (1, 2)) == [1, 2, 3, 4]


def test_rest_voices_only_the_unvoiced_scenes_in_order():
    assert names(JobRequest("synth", "rest"), (1, 3)) == [2, 4]
    assert names(JobRequest("synth", "rest"), (1, 2, 3, 4)) == []


def test_a_single_scene_request_is_that_scene_or_none_when_it_is_gone():
    assert names(JobRequest("synth-scene", scene=3), (1,)) == [3]
    assert names(JobRequest("synth-scene", scene=9)) == []


def plan(titles):
    return json.dumps({"scenes": [{"title": title} for title in titles]}, ensure_ascii=False, indent=2) + "\n"


def test_the_scenes_of_the_whole_stdout_are_counted():
    assert plan_scene_count(plan(["a", "b", "c"])) == 3


def test_unicode_line_separators_in_titles_do_not_break_the_count():
    assert plan_scene_count(plan(["one two", "x\u0085y", "z "])) == 3


@pytest.mark.parametrize("stdout", ["", "not json", "[1]", '"s"', "{}", '{"scenes": 3}', '{"scenes": null}'])
def test_anything_but_an_object_with_a_scenes_list_is_none(stdout):
    assert plan_scene_count(stdout) is None


BODIES = {1: "Hello there.", 2: "Second scene.", 3: "Third one."}
WAVS = {n: f"wav-{n}".encode() for n in BODIES}


def web_scenes():
    return tuple(PlannedScene(n, f"T{n}", body) for n, body in BODIES.items())


def eleven(n, **options):
    return eleven_entry(n, WAVS[n], BODIES[n], **options)


FIXTURES = {
    "record-absent": None,
    "gemini-record": [gemini_entry(n, WAVS[n]) for n in BODIES],
    "elevenlabs-record": [eleven(n) for n in BODIES],
    "body-mismatch": [eleven(1), eleven(2, alignment={"characters": list("Other text."), "character_start_times_seconds": [0.0] * 11, "character_end_times_seconds": [0.1] * 11}), eleven(3)],
    "gemini-scene-among-elevenlabs": [eleven(1), gemini_entry(2, WAVS[2]), eleven(3)],
    "missing-entry": [eleven(1), eleven(3)],
    "hash-mismatch": [eleven(1), eleven(2, sha256="f" * 64), eleven(3)],
}


@pytest.mark.parametrize("name", FIXTURES)
def test_the_estimate_equals_the_number_of_scenes_align_routes_to_transcription_or_every_scene_when_align_fails(tmp_path, name):
    entries = FIXTURES[name]
    if entries is not None:
        write_record(tmp_path, *entries)
    routed = route_record(
        [PlanScene(n, f"T{n}", body) for n, body in BODIES.items()],
        [SceneWav(WAVS[n], 1) for n in BODIES],
        tmp_path,
    )
    estimate = listen_scenes(web_scenes(), read_record(tmp_path, None), {n: sha(WAVS[n]) for n in BODIES})
    if isinstance(routed, str):  # the CLI would fail with its own message: the estimate is the upper bound
        assert name in {"missing-entry", "hash-mismatch"} and estimate == len(BODIES)
    else:
        assert estimate == sum(route is None for route in routed.routes)
    assert estimate == {"elevenlabs-record": 0, "body-mismatch": 1, "gemini-scene-among-elevenlabs": 1}.get(name, 3)


def test_an_unreadable_record_counts_every_scene_as_listened(tmp_path):
    (tmp_path / "synth_record.json").write_text("{")
    assert listen_scenes(web_scenes(), read_record(tmp_path, None), {}) == 3


def test_an_unvoiced_scene_is_listened_and_an_empty_plan_is_zero(tmp_path):
    write_record(tmp_path, *[eleven(n) for n in BODIES])
    record = read_record(tmp_path, None)
    assert listen_scenes(web_scenes(), record, {1: sha(WAVS[1]), 3: sha(WAVS[3])}) == 1
    assert listen_scenes((), record, {}) == 0


JOB_KEYS = [
    "kind", "mode", "project", "scene", "started", "finished", "completed", "total", "scenes_done", "failure", "notice", "run",
]  # fmt: skip


def test_idle_has_no_job() -> None:
    assert current_job_json(JobStatus(), []) == {"state": "idle", "job": None}


def test_a_running_job_has_the_whole_shape_and_no_failure_or_notice() -> None:
    status = status_of("running", scene=2, scenes_done=1, total=4)
    assert current_job_json(status, []) == {
        "state": "running",
        "job": {
            "kind": "synth",
            "mode": "all",
            "project": "my-video",
            "scene": 2,
            "started": True,
            "finished": False,
            "completed": False,
            "total": 4,
            "scenes_done": 1,
            "failure": None,
            "notice": None,
            "run": None,
        },
    }


@pytest.mark.parametrize(
    ("state", "started", "finished", "completed"),
    [
        ("starting", False, False, False),
        ("running", True, False, False),
        ("cancelling", True, False, False),
        ("done", True, True, True),
        ("failed", True, True, False),
        ("cancelled", True, True, False),
    ],
)
def test_the_flags_follow_the_state(state: str, started: bool, finished: bool, completed: bool) -> None:
    job = current_job_json(status_of(state), [])["job"]
    assert isinstance(job, dict)
    assert list(job) == JOB_KEYS
    assert (job["started"], job["finished"], job["completed"]) == (started, finished, completed)


def test_a_notice_rides_along_on_a_finished_job() -> None:
    job = current_job_json(status_of("done", notice="Spare copies remain."), [])["job"]
    assert isinstance(job, dict)
    assert (job["notice"], job["failure"]) == ("Spare copies remain.", None)


def test_a_failed_job_carries_the_failure_worked_out_from_the_events() -> None:
    events = [{"type": "fail", "kind": "quota", "message": "x", "scene": 3, "line": None, "status": 429}]
    status = status_of("failed", failure_kind="other", failure="SceneVoice stopped with an error before the job was finished.")
    job = current_job_json(status, events)["job"]
    assert isinstance(job, dict)
    assert job["failure"] == {"kind": "quota", "message": FIXED_FAILURE, "scene": 3, "status": 429}


def test_a_snapshot_event_is_the_same_json_with_a_type_and_a_seq() -> None:
    status = status_of("running")
    assert snapshot_event("state", 1, status, []) == {"seq": 1, "type": "state", **current_job_json(status, [])}
    assert snapshot_event("end", 9, status, [])["type"] == "end"
