import base64
import os
import sys
import threading
from pathlib import Path

import pytest
from detail_helper import FakePlan, failing_script, snapshot
from job_runner_helper import wait_final, wait_until
from post_job_helper import (
    MODEL,
    PLAN_JSON,
    SCRIPT,
    BlockingPlan,
    JobBed,
    align_body,
    confirm_for,
    synth_all,
    synth_scene,
)

from scenevoice.web import CliResult, build_synth_argv
from scenevoice.web.job_request import UNKNOWN_JOB

NOT_FOUND = "That project does not exist."
SAVE_FIRST = "Save a script first."
FIX_FIRST = "Fix the problems in your script first."
CHANGED = "The script or settings changed since you confirmed. Check the numbers and confirm again."
STARTED = "Voicing has already started for this project. Choose Voice the rest or Start again."
NOTHING = "Nothing has been voiced yet."
DIFFER = "One script uses one voice and model. These settings differ from the ones already used."
CANCELLED = "Cancelled before it started. Nothing was spent."
CHECK_FAILED = "The script could not be checked just now. Try again."


@pytest.fixture
def bed(stub_cli, tmp_path):
    return JobBed(stub_cli(stdout=PLAN_JSON), tmp_path)


def bad_confirm(**changes):
    return synth_all(confirm={**confirm_for(), **changes})


def wavs_exist(bed):
    bed.save_script()
    bed.voice()


def script_problem(bed):
    bed.save_script()
    bed.run = failing_script()


def cli_failure(bed):
    bed.save_script()
    bed.run = FakePlan(CliResult(0, "not a plan", "", False))


def saved(bed):
    bed.save_script()


def voiced(bed):
    bed.save_script()
    bed.voice()


# id: (setup, body, expected (status, kind, message), plan calls)
REFUSALS = {
    "no-script": (lambda bed: None, synth_all(), (409, "not_allowed", SAVE_FIRST), 0),
    "script-problem": (script_problem, synth_all(), (409, "not_allowed", FIX_FIRST), 1),
    "plan-cli-failure": (cli_failure, synth_all(), (502, "cli_failed", CHECK_FAILED), 1),
    "scene-no-longer-in-the-script-is-a-stale-tab": (saved, synth_scene(3), (409, "changed", CHANGED), 1),
    "changed-scenes": (saved, bad_confirm(scenes=3), (409, "changed", CHANGED), 1),
    "changed-model": (saved, bad_confirm(model="other"), (409, "changed", CHANGED), 1),
    "changed-revision": (saved, bad_confirm(revision="0" * 64), (409, "changed", CHANGED), 1),
    "align-changed-revision": (voiced, align_body(confirm={"scenes": 2, "revision": "0" * 64}), (409, "changed", CHANGED), 1),
    "changed-comes-before-not-allowed": (wavs_exist, bad_confirm(characters=1), (409, "changed", CHANGED), 1),
    "all-with-a-wav-present": (wavs_exist, synth_all(), (409, "not_allowed", STARTED), 1),
    "scene-with-nothing-voiced": (saved, synth_scene(2), (409, "not_allowed", NOTHING), 1),
    "scene-settings-differ-from-the-record": (voiced, synth_scene(2, voice="Other"), (409, "not_allowed", DIFFER), 1),
}


@pytest.mark.parametrize("name", REFUSALS)
# Paid call without confirm: a refused start spends nothing and starts no child.
def test_every_refusal_answers_in_order_frees_the_slot_and_starts_no_child(bed, name):
    setup, body, expected, plans = REFUSALS[name]
    setup(bed)
    assert bed.error(body) == expected
    assert len(bed.run.calls) == plans
    assert (bed.runner.job_active(), bed.runner.current().state) == (False, "idle")
    assert bed.children() == [] and bed.launch_files() == []


@pytest.mark.parametrize("name", ["plan-raises", "start-raises"])
def test_an_exception_on_any_path_frees_the_slot_and_removes_the_plan_file(bed, monkeypatch, name):
    bed.save_script()
    module = sys.modules["scenevoice.web.launch_job"]

    def boom(*args, **kwargs):
        raise OSError("boom")

    if name == "plan-raises":
        bed.run = boom
    elif name == "plan-file-cannot-be-written":
        monkeypatch.setattr(module, "write_private_file", boom)
    else:
        monkeypatch.setattr(bed.runner, "start", boom)
    with pytest.raises(OSError):
        bed.post(synth_all())
    assert (bed.runner.job_active(), bed.runner.current().state) == (False, "idle")
    assert bed.children() == [] and bed.launch_files() == []


def test_a_bad_body_is_400_before_the_project_is_looked_up_and_an_unknown_project_is_404(bed):
    assert bed.error({"kind": "play"}) == (400, "bad_request", UNKNOWN_JOB)
    response, parsed = bed.post(synth_all(), bed.other_handler)
    assert (response.status, parsed["error"]) == (404, {"kind": "not_found", "message": NOT_FOUND})
    assert bed.run.calls == [] and bed.runner.current().state == "idle"


def test_a_start_while_a_job_holds_the_slot_is_busy_in_the_words_of_the_running_kind_and_reads_nothing(bed, monkeypatch):
    bed.save_script()
    reads = []
    module = sys.modules["scenevoice.web.begin_job"]
    monkeypatch.setattr(module, "read_script_bytes", lambda *a: reads.append(a))
    held = bed.runner.reserve("beats", "other")
    assert bed.error(synth_all()) == (409, "busy", "SceneVoice is busy planning visual beats.")
    bed.runner.release(held)
    assert reads == [] and bed.run.calls == [] and bed.children() == []


def test_a_cancel_while_the_start_is_inside_plan_holds_the_slot_until_the_start_answers_cancelled(bed):
    bed.save_script()
    bed.run = plan = BlockingPlan()
    answers = []
    thread = threading.Thread(target=lambda: answers.append(bed.error(synth_all())))
    thread.start()
    assert plan.entered.wait(15)
    bed.runner.cancel()
    assert (bed.runner.current().state, bed.runner.job_active()) == ("cancelling", True)
    plan.open.set()
    thread.join(15)
    assert answers == [(409, "busy", CANCELLED)]
    assert (bed.runner.job_active(), bed.runner.current().state) == (False, "idle")
    assert bed.children() == [] and bed.launch_files() == []


def test_plan_runs_once_and_the_child_gets_exactly_the_counted_bytes_in_a_private_file_removed_at_the_end(stub_cli, tmp_path):
    bed = JobBed(stub_cli(stdout=PLAN_JSON, record_files=[1]), tmp_path)
    bed.save_script()
    real = bed.run

    def edits_the_script_after_planning(args, stdin=None, timeout=30.0):
        result = real(args, stdin, timeout)
        (bed.project / "script.md").write_bytes(b"# Other\nChanged after the plan.\n")
        return result

    bed.run = edits_the_script_after_planning
    response, parsed = bed.post(synth_all())
    assert (response.status, parsed["job"]["kind"]) == (202, "synth") and parsed["state"] in ("starting", "running")
    assert wait_final(bed.runner).state == "done"
    assert len(real.calls) == 1
    seen = bed.stub.recording()["files"][0]
    assert seen["mode"] == 0o600 and not os.path.exists(seen["path"])
    assert base64.b64decode(seen["bytes_b64"]) == PLAN_JSON.encode("utf-8")
    assert "é" in PLAN_JSON and "\U0001f600" in PLAN_JSON


def test_a_same_length_edit_between_confirmation_and_start_is_changed_and_touches_nothing(bed):
    bed.save_script()
    confirmed = confirm_for(SCRIPT)
    edited = SCRIPT.replace(b"One", b"Ond")
    assert len(edited) == len(SCRIPT)
    bed.save_script(edited)
    before = snapshot(bed.project)
    assert bed.error(synth_all(confirm=confirmed)) == (409, "changed", CHANGED)
    assert snapshot(bed.project) == before
    assert bed.children() == [] and len(bed.run.calls) == 1


def test_synth_all_answers_202_with_the_current_job_and_the_child_gets_the_built_argv(stub_cli, tmp_path):
    bed = JobBed(stub_cli(stdout=PLAN_JSON), tmp_path)
    bed.save_script()
    response, parsed = bed.post(synth_all(language="en-GB", instruction="Calm"))
    assert response.status == 202
    assert parsed["job"] | {"scenes_done": 0} == parsed["job"]
    assert (parsed["job"]["kind"], parsed["job"]["mode"], parsed["job"]["project"], parsed["job"]["total"]) == ("synth", "all", "p", 2)
    wait_final(bed.runner)
    argv = bed.children()[-1]["argv"]
    assert argv == build_synth_argv(
        Path(argv[1]), bed.project, voice="Leda", model=MODEL, language="en-GB", instruction="Calm", scene=None
    )
    assert argv[1].startswith(str(bed.launch)) and argv[3] == str(bed.project)


def test_synth_scene_takes_its_settings_from_the_record_and_names_the_scene(stub_cli, tmp_path):
    bed = JobBed(stub_cli(stdout=PLAN_JSON), tmp_path)
    bed.save_script()
    bed.voice()
    response, parsed = bed.post(synth_scene(2))
    assert (response.status, parsed["job"]["kind"], parsed["job"]["scene"], parsed["job"]["total"]) == (202, "synth-scene", 2, 1)
    wait_final(bed.runner)
    argv = bed.children()[-1]["argv"]
    assert argv[4:] == ["--voice=Leda", f"--model={MODEL}", "--language=en-GB", "--scene=2", "--progress", "json"]


def test_a_shutdown_that_begins_while_the_start_is_inside_plan_stops_it_before_any_child(bed):
    bed.save_script()
    bed.run = plan = BlockingPlan()
    answers = []
    thread = threading.Thread(target=lambda: answers.append(bed.error(synth_all())))
    thread.start()
    assert plan.entered.wait(15)
    stopper = threading.Thread(target=bed.runner.shutdown)
    stopper.start()
    wait_until(lambda: bed.runner.busy_reason() == "stopping")
    plan.open.set()
    thread.join(15)
    stopper.join(15)
    assert answers == [(409, "busy", "SceneVoice is stopping.")]
    assert bed.children() == [] and bed.launch_files() == []
