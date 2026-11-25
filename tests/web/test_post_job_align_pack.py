import threading
from pathlib import Path

import pytest
from detail_helper import put_record, put_wavs, snapshot
from job_runner_helper import wait_final, wait_until
from post_job_helper import (
    BODIES,
    PACK_BODY,
    PLAN_JSON,
    SCRIPT,
    WAVS,
    BlockingPlan,
    JobBed,
    align_body,
)
from restart_helper import FIXED, bystanders

from scenevoice.web import build_align_argv, build_pack_argv
from scenevoice.web.file_ops import FileOps
from scenevoice.web.restart_messages import NOT_ORDINARY

CHANGED = "The script or settings changed since you confirmed. Check the numbers and confirm again."
VOICE_EVERY = "Voice every scene before this step."
CANCELLED = "Cancelled before it started. Nothing was spent."
WENT_WRONG = "Something went wrong."
PACK_FILES = ("scene_manifest.csv", "resolve_timeline.otio")


@pytest.fixture
def bed(stub_cli, tmp_path):
    bed = JobBed(stub_cli(stdout=PLAN_JSON), tmp_path)
    bed.save_script()
    bed.voice()
    return bed


def eleven_bed(stub_cli, tmp_path):
    bed = JobBed(stub_cli(stdout=PLAN_JSON), tmp_path)
    bed.save_script()
    put_wavs(bed.project, WAVS)
    put_record(bed.project, BODIES, WAVS, eleven=True)
    return bed


# --- align -----------------------------------------------------------------------------------------------------------


def test_align_runs_one_child_over_the_one_counted_plan_file_and_the_folder(bed):
    response, parsed = bed.post(align_body())
    assert response.status == 202 and (parsed["job"]["kind"], parsed["job"]["mode"], parsed["job"]["total"]) == ("align", "align", 2)
    assert wait_final(bed.runner).state == "done"
    (call,) = bed.children()
    assert call["argv"] == build_align_argv(Path(call["argv"][3]), bed.project)
    assert bed.launch_files() == []


def test_the_align_echo_is_the_scenes_that_will_be_listened_to_and_the_revision_so_a_gemini_script_listens_to_every_scene(bed):
    assert bed.error(align_body(1))[:2] == (409, "changed")
    assert bed.error(align_body(0))[:2] == (409, "changed")
    assert bed.children() == []


def test_a_free_run_echoes_zero_and_a_stale_estimate_of_two_is_changed(stub_cli, tmp_path):
    bed = eleven_bed(stub_cli, tmp_path)
    assert bed.error(align_body(2))[:2] == (409, "changed")
    response, _ = bed.post(align_body(0))
    assert response.status == 202
    wait_final(bed.runner)


def test_the_align_revision_is_the_hash_of_the_planned_bytes(bed):
    assert bed.error(align_body(data=SCRIPT + b"\n"))[:2] == (409, "changed")
    assert bed.children() == []


def test_align_needs_every_plan_scene_voiced_and_the_echo_is_judged_first(bed):
    (bed.project / "audio" / "002.wav").unlink()
    assert bed.error(align_body(99)) == (409, "changed", CHANGED)
    assert bed.error(align_body()) == (409, "not_allowed", VOICE_EVERY)
    assert bed.children() == [] and bed.launch_files() == [] and bed.runner.current().state == "idle"


# --- pack ------------------------------------------------------------------------------------------------------------


def old_pack(bed):
    for name in (*PACK_FILES, "line_timings.json"):
        (bed.project / name).write_bytes(f"old {name}".encode())
    return bystanders(bed.project)


def test_pack_takes_no_confirmation_and_runs_one_child_over_the_one_counted_plan_file(bed):
    response, parsed = bed.post(PACK_BODY)
    assert response.status == 202 and (parsed["job"]["kind"], parsed["job"]["mode"]) == ("pack", "pack")
    assert wait_final(bed.runner).state == "done"
    (call,) = bed.children()
    assert call["argv"] == build_pack_argv(Path(call["argv"][5]), bed.project)
    assert Path(call["argv"][5]).parent == bed.launch and bed.launch_files() == []


def test_pack_deletes_the_old_manifest_and_timeline_before_the_child_starts_and_keeps_everything_else(bed, monkeypatch):
    kept = old_pack(bed)
    seen = []
    real = bed.runner.start
    monkeypatch.setattr(bed.runner, "start", lambda *a: (seen.append([n for n in PACK_FILES if (bed.project / n).exists()]), real(*a))[1])
    before = snapshot(bed.project)
    assert bed.post(PACK_BODY)[0].status == 202
    wait_final(bed.runner)
    assert seen == [[]]
    after = snapshot(bed.project)
    assert set(before) - set(after) == set(PACK_FILES) and (bed.project / "line_timings.json").read_bytes() == b"old line_timings.json"
    assert all((bed.project / name).read_bytes() == data for name, data in kept.items())


def test_a_failed_pack_leaves_the_old_pack_gone(stub_cli, tmp_path):
    bed = JobBed(stub_cli(stdout=PLAN_JSON, exit_code=1), tmp_path)
    bed.save_script()
    bed.voice()
    old_pack(bed)
    bed.post(PACK_BODY)
    assert wait_final(bed.runner).state == "failed"
    assert not any((bed.project / name).exists() for name in PACK_FILES)


def test_pack_with_a_scene_not_voiced_is_refused_and_deletes_nothing(bed):
    old_pack(bed)
    (bed.project / "audio" / "001.wav").unlink()
    before = snapshot(bed.project)
    assert bed.error(PACK_BODY) == (409, "not_allowed", VOICE_EVERY)
    assert snapshot(bed.project) == before and bed.children() == [] and bed.launch_files() == []


def test_a_pack_output_that_is_not_an_ordinary_file_refuses_the_start_and_deletes_nothing(bed, tmp_path):
    old_pack(bed)
    (bed.project / "resolve_timeline.otio").unlink()
    (bed.project / "resolve_timeline.otio").symlink_to(tmp_path / "elsewhere")
    before = sorted(p.name for p in bed.project.rglob("*"))
    assert bed.error(PACK_BODY) == (409, "not_allowed", NOT_ORDINARY)
    assert sorted(p.name for p in bed.project.rglob("*")) == before
    assert bed.children() == [] and bed.launch_files() == [] and bed.runner.current().state == "idle"


def test_a_deletion_that_fails_answers_something_went_wrong_frees_the_slot_and_starts_no_child(stub_cli, tmp_path):
    def failing(path):
        raise OSError("disk says no")

    bed = JobBed(stub_cli(stdout=PLAN_JSON), tmp_path, ops=FileOps(unlink=failing))
    bed.save_script()
    bed.voice()
    old_pack(bed)
    assert bed.error(PACK_BODY) == (500, "internal_error", WENT_WRONG)
    assert bed.children() == [] and not bed.runner.job_active() and bed.launch_files() == []


@pytest.mark.parametrize("how", ["cancel", "shutdown"])
def test_a_cancel_or_shutdown_during_the_plan_stops_the_pack_before_any_file_is_deleted(bed, how):
    old_pack(bed)
    bed.run = plan = BlockingPlan(BODIES)
    answers = []
    thread = threading.Thread(target=lambda: answers.append(bed.error(PACK_BODY)))
    thread.start()
    assert plan.entered.wait(15)
    if how == "cancel":
        bed.runner.cancel()
    else:
        threading.Thread(target=bed.runner.shutdown).start()
        wait_until(lambda: bed.runner.busy_reason() == "stopping")
    plan.open.set()
    thread.join(15)
    assert answers == [(409, "busy", CANCELLED if how == "cancel" else "SceneVoice is stopping.")]
    assert all((bed.project / name).exists() for name in FIXED[2:]) and bed.children() == []
