import json
import os
import threading
from pathlib import Path

import pytest
from detail_helper import passing
from job_runner_helper import wait_final, wait_started, wait_until
from post_job_helper import (
    BODIES3,
    MODEL,
    SCRIPT3,
    BlockingPlan,
    JobBed,
    confirm_for,
    synth_restart,
)
from restart_helper import bystanders, old_generation, snapshot

from scenevoice.web import build_synth_argv
from scenevoice.web.file_ops import FileOps
from scenevoice.web.restart_messages import NOT_ORDINARY, ROLLBACK_FAILED
from scenevoice.web.scan_backups import scan_backups

CHANGED = "The script or settings changed since you confirmed. Check the numbers and confirm again."
NOTHING = "Nothing has been voiced yet."
MISMATCH = "What was voiced does not match this script or these settings. Choose Start again."
DIFFER = "One script uses one voice and model. These settings differ from the ones already used."
ALL_VOICED = "Every scene is already voiced."
CANCELLED = "Cancelled before it started. Nothing was spent."
NOTHING_SPENT_STOPPING = "SceneVoice is stopping."


def done_line(scene: int, total: int = 3) -> str:
    return json.dumps({"command": "synth", "event": "scene", "message": "done", "state": "done", "scene": scene, "total": total})


def restart_body(**changes):
    return synth_restart(**{"confirm": confirm_for(SCRIPT3, BODIES3), **changes})


# --- restart (Start again) -------------------------------------------------------------------------------------------


def restart_bed(stub_cli, tmp_path, ops=None, **spec):
    bed = JobBed(stub_cli(**spec), tmp_path, run=passing(BODIES3), ops=ops)
    bed.old = old_generation(bed.project)
    bed.keep = bystanders(bed.project)
    bed.save_script(SCRIPT3)  # the bystander `script.md` is the real script
    bed.keep["script.md"] = SCRIPT3
    bed.before = snapshot(bed.project)
    return bed


def backups(bed) -> list[str]:
    return sorted(str(p.relative_to(bed.project)) for p in bed.project.rglob(".write-restart-*"))


def test_restart_sets_the_old_generation_aside_only_after_the_echo_check_and_before_the_child_starts(stub_cli, tmp_path):
    hold = tmp_path / "hold"
    bed = restart_bed(stub_cli, tmp_path, wait_for_file=str(hold))
    assert bed.error(restart_body(confirm={**confirm_for(SCRIPT3, BODIES3), "characters": 1}))[:2] == (409, "changed")
    assert snapshot(bed.project) == bed.before and backups(bed) == []
    response, _ = bed.post(restart_body())
    assert response.status == 202
    wait_started(bed.stub)
    assert len(backups(bed)) == len(bed.old)  # the line markers, the manifest and the timeline are set aside with the audio
    assert not any((bed.project / name).exists() for name in bed.old)
    assert {k: v for k, v in snapshot(bed.project).items() if ".write-restart-" not in k} == bed.keep
    hold.write_text("go")
    assert wait_final(bed.runner).state == "done"
    plan_file = bed.children()[0]["argv"][1]
    assert bed.children()[0]["argv"] == build_synth_argv(
        Path(plan_file), bed.project, voice="Leda", model=MODEL, language=None, instruction=None, scene=None
    )
    assert snapshot(bed.project) == bed.keep and bed.runner.current().scenes_done == 0


def test_a_file_that_is_not_ordinary_refuses_the_whole_restart_and_changes_nothing(stub_cli, tmp_path):
    bed = restart_bed(stub_cli, tmp_path)
    (bed.project / "line_timings.json").unlink()
    (bed.project / "line_timings.json").symlink_to(tmp_path / "elsewhere")
    before = sorted(p.name for p in bed.project.rglob("*"))
    assert bed.error(restart_body()) == (409, "not_allowed", NOT_ORDINARY)
    assert sorted(p.name for p in bed.project.rglob("*")) == before
    assert bed.children() == [] and bed.launch_files() == [] and bed.runner.current().state == "idle"


@pytest.mark.parametrize("how", ["cancel", "shutdown"])
def test_a_cancel_or_shutdown_during_the_plan_stops_the_restart_before_any_file_is_moved(stub_cli, tmp_path, how):
    renames = []
    ops = FileOps(rename=lambda a, b: renames.append((a, b)))
    bed = restart_bed(stub_cli, tmp_path, ops)
    bed.run = plan = BlockingPlan(BODIES3)
    answers = []
    thread = threading.Thread(target=lambda: answers.append(bed.error(restart_body())))
    thread.start()
    assert plan.entered.wait(15)
    if how == "cancel":
        bed.runner.cancel()
    else:
        threading.Thread(target=bed.runner.shutdown).start()
        wait_until(lambda: bed.runner.busy_reason() == "stopping")
    plan.open.set()
    thread.join(15)
    assert answers == [(409, "busy", CANCELLED if how == "cancel" else NOTHING_SPENT_STOPPING)]
    assert renames == [] and snapshot(bed.project) == bed.before and bed.children() == []


def test_a_failure_before_any_scene_is_done_puts_the_whole_old_generation_back(stub_cli, tmp_path):
    spec = {"write_files": {str(tmp_path / "ws" / "p" / "audio" / "001.wav"): "NEW"}, "exit_code": 1}
    bed = restart_bed(stub_cli, tmp_path, **spec)
    bed.post(restart_body())
    final = wait_final(bed.runner)
    assert final.state == "failed" and final.notice is None
    assert snapshot(bed.project) == bed.before and backups(bed) == []


def test_a_cancel_in_that_window_puts_the_whole_old_generation_back_and_ends_cancelled(stub_cli, tmp_path):
    spec = {"write_files": {str(tmp_path / "ws" / "p" / "audio" / "001.wav"): "NEW"}, "sleep": 30, "sigint": "exit", "sigint_exit_code": 130}
    bed = restart_bed(stub_cli, tmp_path, **spec)
    bed.post(restart_body())
    wait_started(bed.stub)
    bed.runner.cancel()
    assert wait_final(bed.runner).state == "cancelled"
    assert snapshot(bed.project) == bed.before and backups(bed) == []


def test_a_failure_after_the_first_done_scene_commits_the_new_generation_and_nothing_of_the_old_returns(stub_cli, tmp_path):
    spec = {"write_files": {str(tmp_path / "ws" / "p" / "audio" / "001.wav"): "NEW"}, "stderr_lines": [done_line(1)], "exit_code": 1}
    bed = restart_bed(stub_cli, tmp_path, **spec)
    bed.post(restart_body())
    final = wait_final(bed.runner)
    assert (final.state, final.scenes_done) == ("failed", 1)
    assert snapshot(bed.project) == {**bed.keep, "audio/001.wav": b"NEW"} and backups(bed) == []


def failing_ops(**broken):
    real = FileOps()
    return FileOps(**{name: broken.get(name, getattr(real, name)) for name in ("rename", "copy", "replace", "unlink")})


def always(error):
    def boom(*args):
        raise error

    return boom


def test_a_rollback_that_cannot_complete_keeps_every_backup_and_the_job_fails_with_the_put_back_message_even_when_cancelled(stub_cli, tmp_path):
    spec = {"sleep": 30, "sigint": "exit", "sigint_exit_code": 130}
    bed = restart_bed(stub_cli, tmp_path, failing_ops(copy=always(OSError("full"))), **spec)
    bed.post(restart_body())
    wait_started(bed.stub)
    bed.runner.cancel()
    final = wait_final(bed.runner)
    assert (final.state, final.failure_kind, final.failure) == ("failed", "other", ROLLBACK_FAILED)
    assert len(backups(bed)) == len(bed.old) and scan_backups(bed.project)
    assert not list(bed.project.rglob(".write-restore-*"))


def test_a_rename_that_fails_part_way_puts_back_the_ones_moved_and_answers_500(stub_cli, tmp_path):
    count = [0]

    def rename(a, b):
        count[0] += 1
        if count[0] == 3:
            raise OSError("no")
        os.rename(a, b)

    bed = restart_bed(stub_cli, tmp_path, failing_ops(rename=rename))
    assert bed.error(restart_body()) == (500, "internal_error", "Something went wrong.")
    assert snapshot(bed.project) == bed.before and backups(bed) == []
    assert bed.children() == [] and bed.launch_files() == [] and bed.runner.current().state == "idle"


def test_a_put_back_that_fails_after_a_partial_set_aside_answers_500_with_the_put_back_message_and_keeps_the_backups(stub_cli, tmp_path):
    count = [0]

    def rename(a, b):
        count[0] += 1
        if count[0] == 3:
            raise OSError("no")
        os.rename(a, b)

    bed = restart_bed(stub_cli, tmp_path, failing_ops(rename=rename, copy=always(OSError("full"))))
    assert bed.error(restart_body()) == (500, "internal_error", ROLLBACK_FAILED)
    assert len(backups(bed)) == 2 and scan_backups(bed.project)


@pytest.mark.parametrize("exit_by", ["plan-file", "spawn", "slot-refused"])
def test_every_exit_after_the_set_aside_and_before_the_start_puts_this_attempts_files_back(stub_cli, tmp_path, monkeypatch, exit_by):
    from scenevoice.web import SlotRefused

    bed = restart_bed(stub_cli, tmp_path)
    module = __import__("sys").modules["scenevoice.web.launch_job"]
    if exit_by == "plan-file":
        monkeypatch.setattr(module, "write_private_file", always(OSError("no")))
    else:
        monkeypatch.setattr(bed.runner, "start", always(OSError("no") if exit_by == "spawn" else SlotRefused("gone")))
    if exit_by == "slot-refused":
        assert bed.error(restart_body()) == (409, "busy", CANCELLED)
    else:
        with pytest.raises(OSError):
            bed.post(restart_body())
    assert snapshot(bed.project) == bed.before and backups(bed) == []
    assert bed.runner.current().state == "idle" and bed.launch_files() == []


def test_an_earlier_kept_backup_survives_both_a_committed_and_a_rolled_back_restart(stub_cli, tmp_path):
    for exit_code, stderr in ((0, [done_line(1)]), (1, [])):
        bed = restart_bed(stub_cli, tmp_path / str(exit_code), exit_code=exit_code, stderr_lines=stderr)
        earlier = bed.project / "audio" / ".write-restart-0f0f-001.wav.tmp"
        earlier.write_bytes(b"recovery file")
        bed.post(restart_body())
        wait_final(bed.runner)
        assert earlier.read_bytes() == b"recovery file"
