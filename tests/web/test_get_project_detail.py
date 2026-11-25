import json
import os
import sys
import threading

import pytest
from detail_helper import (
    FakePlan,
    failing_script,
    passing,
    put_record,
    put_wavs,
    sha,
)
from line_markers_helper import write_timings
from web_http_helper import make_request

from scenevoice.web import CliResult, get_project_detail

BODIES = ["Caf\xe9 one.", "Two \U0001f600 here."]
SCRIPT = b"# One\nCaf\xc3\xa9 one.\n\n# Two\nTwo \xf0\x9f\x98\x80 here.\n"
WAVS = {1: b"wav-one", 2: b"wav-two"}
NO_PROJECT = "That project does not exist."


@pytest.fixture
def launch(tmp_path):
    directory = tmp_path / "launch"
    directory.mkdir(mode=0o700)
    return directory


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "ws"
    (root / "p").mkdir(parents=True)
    return root / "p"


@pytest.fixture
def detail(project, launch):
    def call(run=None, *, job_active=False, key_file=None, project_id="p"):
        handler = get_project_detail(
            lambda: project.parent, project_id, key_file, run or passing(BODIES), launch, threading.Lock(), lambda: job_active
        )
        response = handler(make_request("GET", f"/api/projects/{project_id}"))
        return response, json.loads(response.body)

    return call


EMPTY = {
    "script": {"present": False, "ok": False, "revision": None, "problem": None, "scenes": [], "total_characters": 0},
    "audio": {"scenes": [], "extra_ordinals": [], "record": "none", "settings": None},
    "line_markers": {"state": "none", "stale_scenes": [], "listen_scenes": 0},
    "beats": {"state": "none"},
    "pack": {"manifest": False, "timeline": False},
    "kept_backups": False,
    "can": {
        "synth": {"all": False, "rest": False, "restart": False},
        "synth_scene": False, "align": False, "beats": False, "beats_redo": False, "pack": False,
    },
}


def test_an_unknown_or_invalid_project_is_404_and_runs_no_plan(detail):
    run = passing(BODIES)
    for project_id in ("nope", "Bad_Id"):
        response, body = detail(run, project_id=project_id)
        assert (response.status, body["error"]) == (404, {"kind": "not_found", "message": NO_PROJECT})
    assert run.calls == []


def test_an_empty_project_is_the_whole_shape_with_nothing_set_and_no_plan_run(detail):
    run = passing(BODIES)
    response, body = detail(run)
    assert (response.status, response.no_store, body) == (200, True, EMPTY)
    assert run.calls == []


def test_a_saved_script_gives_scenes_with_code_point_characters_total_and_revision(detail, project):
    (project / "script.md").write_bytes(SCRIPT)
    run = passing(BODIES)
    _, body = detail(run)
    assert [(s["ordinal"], s["title"]) for s in body["script"]["scenes"]] == [(1, "Scene 1"), (2, "Scene 2")]
    assert (body["script"]["present"], body["script"]["ok"], body["script"]["problem"]) == (True, True, None)
    assert [s["characters"] for s in body["script"]["scenes"]] == [len(BODIES[0]), len(BODIES[1])]
    assert body["script"]["total_characters"] == len(BODIES[0]) + len(BODIES[1])
    assert body["script"]["revision"] == sha(SCRIPT) and len(run.calls) == 1


def test_the_revision_changes_when_text_is_edited_without_changing_length_or_scene_count(detail, project):
    (project / "script.md").write_bytes(b"abc one\n")
    first = detail()[1]["script"]["revision"]
    (project / "script.md").write_bytes(b"abd one\n")
    second = detail()[1]["script"]["revision"]
    assert first != second and len(first) == len(second) == 64


def test_a_script_with_a_problem_is_200_with_the_one_problem_and_no_scenes(detail, project):
    (project / "script.md").write_bytes(SCRIPT)
    response, body = detail(failing_script(4, "Scene 2 is empty"))
    assert response.status == 200
    assert body["script"] == {
        "present": True, "ok": False, "revision": sha(SCRIPT), "problem": {"line": 4, "message": "Scene 2 is empty"},
        "scenes": [], "total_characters": 0,
    }
    assert body["can"] == EMPTY["can"]


def test_a_plan_cli_failure_is_502_cli_failed_in_plain_words(detail, project):
    (project / "script.md").write_bytes(SCRIPT)
    response, body = detail(FakePlan(CliResult(-1, "", "", True)))
    assert (response.status, body["error"]["kind"], body["error"]["message"]) == (
        502, "cli_failed", "The script could not be checked just now. Try again.",
    )


@pytest.mark.parametrize(
    ("make", "message", "revision"),
    [
        pytest.param(lambda p: os.symlink(p / "real.md", p / "script.md"), "The script in this project is not an ordinary text file, so it cannot be opened here.", None, id="symlink"),
        pytest.param(lambda p: (p / "script.md").write_bytes(b"x" * (1024 * 1024 + 1)), "The script in this project is larger than 1 MiB, so it cannot be opened here.", None, id="too-large"),
        pytest.param(lambda p: (p / "script.md").write_bytes(b"\xff\xfe bad"), "The script in this project is not valid UTF-8 text, so it cannot be opened here.", sha(b"\xff\xfe bad"), id="not-utf8"),
    ],
)
def test_a_script_that_cannot_be_read_is_a_problem_and_runs_no_plan(detail, project, make, message, revision):
    (project / "real.md").write_bytes(b"x")
    make(project)
    run = passing(BODIES)
    response, body = detail(run)
    assert response.status == 200 and run.calls == []
    assert body["script"]["problem"] == {"line": None, "message": message}
    assert (body["script"]["present"], body["script"]["ok"]) == (True, False)
    assert body["script"]["revision"] == revision


def voiced_project(project, eleven=False):
    (project / "script.md").write_bytes(SCRIPT)
    put_wavs(project, WAVS)
    put_record(project, BODIES, WAVS, eleven=eleven)


def test_a_voiced_gemini_project_reports_each_scene_and_the_common_settings(detail, project):
    voiced_project(project)
    _, body = detail()
    assert body["audio"] == {
        "scenes": [
            {"ordinal": 1, "voiced": True, "recorded": True, "wav_matches_record": True, "text_matches": None},
            {"ordinal": 2, "voiced": True, "recorded": True, "wav_matches_record": True, "text_matches": None},
        ],
        "extra_ordinals": [], "record": "ok",
        "settings": {"voice": "Leda", "model": "gemini-3.8-flash-tts", "language": "en-GB", "instruction": None},
    }


def test_text_matches_follows_the_record_alignment_and_is_false_for_an_edited_script(detail, project):
    voiced_project(project, eleven=True)
    assert [s["text_matches"] for s in detail()[1]["audio"]["scenes"]] == [True, True]
    _, edited = detail(passing(["Caf\xe9 one.", "Changed words."]))
    assert [s["text_matches"] for s in edited["audio"]["scenes"]] == [True, False]
    assert edited["can"]["synth"]["rest"] is False  # the false witness refuses voicing the rest


def test_a_fresh_line_timings_entry_is_the_witness_for_a_gemini_scene(detail, project):
    voiced_project(project)
    write_timings(project, [(1, sha(WAVS[1]), [0]), (2, sha(WAVS[2]), [0])])
    (project / "line_timings.json").write_text(json.dumps({"scenes": [
        {"ordinal": 1, "sha256": sha(WAVS[1]), "lines": [{"text": "Caf\xe9 one.", "start_ms": 0}]},
        {"ordinal": 2, "sha256": sha(b"other"), "lines": [{"text": "Two", "start_ms": 0}]},
    ]}))
    scenes = detail()[1]["audio"]["scenes"]
    assert [s["text_matches"] for s in scenes] == [True, None]  # scene 2's entry is stale: no witness


def test_a_wav_that_differs_from_the_record_is_flagged_and_an_unreadable_record_is_reported(detail, project):
    voiced_project(project)
    (project / "audio" / "002.wav").write_bytes(b"changed")
    scenes = detail()[1]["audio"]["scenes"]
    assert [s["wav_matches_record"] for s in scenes] == [True, False]
    (project / "synth_record.json").write_text("{")
    audio = detail()[1]["audio"]
    assert (audio["record"], audio["settings"]) == ("unreadable", None)
    assert [s["recorded"] for s in audio["scenes"]] == [False, False]


def test_mixed_recorded_settings_give_no_common_settings(detail, project):
    voiced_project(project)
    record = json.loads((project / "synth_record.json").read_text())
    record["scenes"][1]["voice"] = "Zephyr"
    (project / "synth_record.json").write_text(json.dumps(record))
    audio = detail()[1]["audio"]
    assert audio["record"] == "ok" and audio["settings"] is None


def test_the_key_file_is_never_read_as_the_record(detail, project):
    voiced_project(project)
    assert detail(key_file=project / "synth_record.json")[1]["audio"]["record"] == "unreadable"


def test_line_markers_report_state_stale_scenes_and_the_listen_estimate(detail, project):
    voiced_project(project)
    assert detail()[1]["line_markers"] == {"state": "none", "stale_scenes": [], "listen_scenes": 2}
    write_timings(project, [(1, sha(WAVS[1]), [0]), (2, sha(WAVS[2]), [0])])
    assert detail()[1]["line_markers"] == {"state": "fresh", "stale_scenes": [], "listen_scenes": 2}
    write_timings(project, [(1, sha(WAVS[1]), [0]), (2, "9" * 64, [0])])
    assert detail()[1]["line_markers"]["stale_scenes"] == [2]
    (project / "line_timings.json").write_text("{")
    assert detail()[1]["line_markers"]["state"] == "unreadable"


def test_beats_state_follows_the_script_revision(detail, project):
    (project / "script.md").write_bytes(SCRIPT)
    sidecar = {"version": 1, "script_sha256": sha(SCRIPT), "scenes": []}
    (project / "beats.json").write_text(json.dumps(sidecar))
    assert detail()[1]["beats"] == {"state": "fresh"}
    (project / "script.md").write_bytes(SCRIPT + b"\n")
    assert detail()[1]["beats"] == {"state": "stale"}
    (project / "beats.json").write_text("[]")
    assert detail()[1]["beats"] == {"state": "invalid"}


def test_the_pack_reports_the_manifest_and_the_timeline_separately(detail, project):
    (project / "scene_manifest.csv").write_text("x")
    assert detail()[1]["pack"] == {"manifest": True, "timeline": False}
    (project / "resolve_timeline.otio").write_text("{}")
    assert detail()[1]["pack"] == {"manifest": True, "timeline": True}


def test_kept_backups_is_true_for_an_exact_backup_file_and_null_while_a_job_holds_the_slot(detail, project):
    assert detail()[1]["kept_backups"] is False
    (project / "audio").mkdir()
    (project / "audio" / ".write-restart-0a1b-001.wav.tmp").write_bytes(b"x")
    assert detail()[1]["kept_backups"] is True
    assert detail(job_active=True)[1]["kept_backups"] is None


def test_can_flags_are_the_availability_table_over_what_was_read(detail, project):
    voiced_project(project)
    assert detail()[1]["can"] == {
        "synth": {"all": False, "rest": False, "restart": True},
        "synth_scene": True, "align": True, "beats": True, "beats_redo": False, "pack": True,
    }


def test_names_outside_the_fixed_list_are_never_read(detail, project, monkeypatch):
    voiced_project(project)
    (project / ".write-restart-0a1b-synth_record.json.tmp").write_text("garbage")
    (project / ".write-beats-0a1b.tmp").write_text("garbage")
    (project / "notes.txt").write_text("garbage")
    seen = []
    target = sys.modules["scenevoice.web.read_regular_bytes"].os  # the one `os` every no-follow open goes through
    real = target.open
    monkeypatch.setattr(target, "open", lambda path, *a, **k: seen.append(os.path.basename(path)) or real(path, *a, **k))
    detail()
    seen = [name for name in seen if not name.startswith("plan-")]  # the server's own temp file for the plan
    assert seen and set(seen) <= {"script.md", "synth_record.json", "line_timings.json", "beats.json", "001.wav", "002.wav"}
