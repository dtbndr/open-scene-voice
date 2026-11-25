import base64
import os
import re
import stat
import threading

import pytest
from beats_sidecar_helper import sidecar_bytes
from detail_helper import snapshot
from job_runner_helper import wait_final, wait_until
from post_job_helper import (
    BEATS_MODEL,
    PLAN_JSON,
    SCRIPT,
    BlockingPlan,
    JobBed,
    beats_body,
    confirm_for,
    sha,
)

from scenevoice.web import build_beats_argv
from scenevoice.web.beats_messages import BEATS_UNREADABLE
from scenevoice.web.job_availability import BEATS_EXIST, NO_BEATS
from scenevoice.web.restart_messages import NOT_ORDINARY

CHANGED = "The script or settings changed since you confirmed. Check the numbers and confirm again."
CANCELLED = "Cancelled before it started. Nothing was spent."
STOPPING = "SceneVoice is stopping."
RUN_FAILURE = "SceneVoice stopped with an error before the job was finished."
GOOD = sidecar_bytes(sha(SCRIPT))
OLD = b'{"old": "beats"}'
CANDIDATE = re.compile(r"\.write-beats-[0-9a-f]+\.tmp")


def beats_bed(stub_cli, tmp_path, out=GOOD, **spec):
    stub = stub_cli(stdout=PLAN_JSON, **({"write_out_hex": out.hex()} if out is not None else {}), **spec)
    bed = JobBed(stub, tmp_path)
    bed.save_script()
    return bed


def old_beats(bed):
    (bed.project / "beats.json").write_bytes(OLD)


def entries(bed):
    return sorted(os.listdir(bed.project))


# --- the start -------------------------------------------------------------------------------------------------------


def test_beats_runs_one_child_on_a_private_script_copy_into_a_candidate_in_the_project_folder_and_creates_beats_json(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path, record_files=[1])
    response, parsed = bed.post(beats_body())
    assert response.status == 202 and (parsed["job"]["kind"], parsed["job"]["mode"], parsed["job"]["total"]) == ("beats", "beats", 2)
    assert wait_final(bed.runner).state == "done"
    (call,) = bed.children()
    script_copy = call["argv"][1]
    candidate = call["argv"][3]
    assert call["argv"] == build_beats_argv(script_copy, candidate, BEATS_MODEL)
    assert os.path.dirname(candidate) == str(bed.project) and CANDIDATE.fullmatch(os.path.basename(candidate))
    assert os.path.dirname(script_copy) == str(bed.launch)
    seen = bed.stub.recording()["files"][0]
    assert seen["mode"] == 0o600 and base64.b64decode(seen["bytes_b64"]) == SCRIPT
    assert (bed.project / "beats.json").read_bytes() == GOOD and entries(bed) == ["beats.json", "script.md"]
    assert bed.launch_files() == [] and len(bed.run.calls) == 1


def test_redo_beats_replaces_the_old_beats_only_when_the_new_set_passes(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path)
    old_beats(bed)
    response, _ = bed.post(beats_body(redo=True))
    assert response.status == 202 and wait_final(bed.runner).state == "done"
    assert (bed.project / "beats.json").read_bytes() == GOOD and entries(bed) == ["beats.json", "script.md"]


# --- refusals --------------------------------------------------------------------------------------------------------


def test_beats_is_refused_when_beats_json_exists_even_as_a_dangling_symlink_and_nothing_changes(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path)
    (bed.project / "beats.json").symlink_to(tmp_path / "nowhere")
    (bed.project / ".write-beats-aa.tmp").write_bytes(b"leftover")
    before = entries(bed)
    assert bed.error(beats_body()) == (409, "not_allowed", BEATS_EXIST)
    assert entries(bed) == before and bed.children() == [] and bed.launch_files() == [] and bed.runner.current().state == "idle"
    (bed.project / "beats.json").unlink()
    old_beats(bed)
    assert bed.error(beats_body()) == (409, "not_allowed", BEATS_EXIST)


def test_redo_beats_is_refused_when_there_are_no_beats(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path)
    assert bed.error(beats_body(redo=True)) == (409, "not_allowed", NO_BEATS)
    assert bed.children() == [] and bed.launch_files() == [] and entries(bed) == ["script.md"]


def make_symlink(bed, tmp_path):
    (tmp_path / "elsewhere.json").write_bytes(GOOD)
    (bed.project / "beats.json").symlink_to(tmp_path / "elsewhere.json")


def make_hard_link(bed, tmp_path):
    (tmp_path / "elsewhere.json").write_bytes(GOOD)
    os.link(tmp_path / "elsewhere.json", bed.project / "beats.json")


@pytest.mark.parametrize("make", [make_symlink, make_hard_link])  # write outside the project
def test_redo_beats_is_refused_when_beats_json_is_not_an_ordinary_file_and_only_a_leftover_candidate_is_swept(stub_cli, tmp_path, make):
    bed = beats_bed(stub_cli, tmp_path)
    make(bed, tmp_path)
    (bed.project / ".write-beats-aa.tmp").write_bytes(b"leftover")
    before = (entries(bed), os.path.exists(tmp_path / "elsewhere.json") and (tmp_path / "elsewhere.json").read_bytes())
    before[0].remove(".write-beats-aa.tmp")  # the sweep runs before the plain-file check, so a leftover candidate goes even when the start is refused
    assert bed.error(beats_body(redo=True)) == (409, "not_allowed", NOT_ORDINARY)
    assert (entries(bed), os.path.exists(tmp_path / "elsewhere.json") and (tmp_path / "elsewhere.json").read_bytes()) == before
    assert bed.children() == [] and bed.launch_files() == [] and bed.runner.current().state == "idle"


@pytest.mark.parametrize("change", ["scenes", "characters", "model", "revision"])
# Paid call without confirm: each confirm field is compared before anything is touched.
def test_every_part_of_the_echo_is_compared_before_anything_is_touched(stub_cli, tmp_path, change):
    bed = beats_bed(stub_cli, tmp_path)
    leftover = bed.project / ".write-beats-0123456789abcdef.tmp"
    leftover.write_bytes(b"half")
    wrong = {"scenes": 3, "characters": 1, "model": "other/model", "revision": "0" * 64}[change]
    assert bed.error(beats_body(confirm={**confirm_for(model=BEATS_MODEL), change: wrong})) == (409, "changed", CHANGED)
    assert leftover.exists() and bed.children() == [] and bed.launch_files() == []


def test_a_same_length_edit_between_confirmation_and_start_is_changed_and_sweeps_nothing(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path)
    leftover = bed.project / ".write-beats-0123456789abcdef.tmp"
    leftover.write_bytes(b"half")
    confirmed = confirm_for(SCRIPT, model=BEATS_MODEL)
    edited = SCRIPT.replace(b"One", b"Ond")
    assert len(edited) == len(SCRIPT)
    bed.save_script(edited)
    before = snapshot(bed.project)
    assert bed.error(beats_body(confirm=confirmed)) == (409, "changed", CHANGED)
    assert snapshot(bed.project) == before and bed.children() == []


@pytest.mark.parametrize("model", [""])
def test_a_model_that_is_empty_too_long_or_holds_a_nul_is_a_bad_request(stub_cli, tmp_path, model):
    bed = beats_bed(stub_cli, tmp_path)
    assert bed.error(beats_body(model=model, confirm=confirm_for(model="m")))[:2] == (400, "bad_request")
    assert bed.children() == []


def test_a_script_problem_or_no_script_is_refused_before_any_file_is_made(stub_cli, tmp_path):
    bed = JobBed(stub_cli(stdout=PLAN_JSON), tmp_path)
    assert bed.error(beats_body()) == (409, "not_allowed", "Save a script first.")
    assert os.listdir(bed.project) == [] and bed.launch_files() == []


@pytest.mark.parametrize("how", ["cancel", "shutdown"])
def test_a_cancel_or_shutdown_during_the_plan_stops_beats_before_any_sweep_or_file(stub_cli, tmp_path, how):
    bed = beats_bed(stub_cli, tmp_path)
    leftover = bed.project / ".write-beats-0123456789abcdef.tmp"
    leftover.write_bytes(b"half")
    bed.run = plan = BlockingPlan()
    answers = []
    thread = threading.Thread(target=lambda: answers.append(bed.error(beats_body())))
    thread.start()
    assert plan.entered.wait(15)
    if how == "cancel":
        bed.runner.cancel()
    else:
        threading.Thread(target=bed.runner.shutdown).start()
        wait_until(lambda: bed.runner.busy_reason() == "stopping")
    plan.open.set()
    thread.join(15)
    assert answers == [(409, "busy", CANCELLED if how == "cancel" else STOPPING)]
    assert leftover.read_bytes() == b"half" and bed.children() == [] and bed.launch_files() == []


def test_an_exception_while_starting_frees_the_slot_and_removes_the_script_copy(stub_cli, tmp_path, monkeypatch):
    bed = beats_bed(stub_cli, tmp_path)

    def boom(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(bed.runner, "start", boom)
    with pytest.raises(OSError):
        bed.post(beats_body())
    assert (bed.runner.job_active(), bed.runner.current().state) == (False, "idle")
    assert bed.children() == [] and bed.launch_files() == [] and entries(bed) == ["script.md"]


# --- the end of the job ----------------------------------------------------------------------------------------------


def finish(bed, body):
    response, _ = bed.post(body)
    assert response.status == 202
    return wait_final(bed.runner)


@pytest.mark.parametrize("redo", [True])
def test_a_shape_invalid_reply_the_cli_wrote_before_exiting_1_is_deleted_and_the_old_beats_stay(stub_cli, tmp_path, redo):
    bed = beats_bed(stub_cli, tmp_path, out=b'{"version": 1, "script_sha256": "bad"}', exit_code=1)
    if redo:
        old_beats(bed)
    final = finish(bed, beats_body(redo=redo))
    assert final.state == "failed"
    assert entries(bed) == (["beats.json", "script.md"] if redo else ["script.md"])
    assert not redo or (bed.project / "beats.json").read_bytes() == OLD


@pytest.mark.parametrize("exit_code", [0])
def test_a_half_written_candidate_never_becomes_beats_json(stub_cli, tmp_path, exit_code):
    bed = beats_bed(stub_cli, tmp_path, out=GOOD[:30], exit_code=exit_code)
    old_beats(bed)
    final = finish(bed, beats_body(redo=True))
    assert final.state == "failed" and (final.failure == BEATS_UNREADABLE if exit_code == 0 else True)
    assert entries(bed) == ["beats.json", "script.md"] and (bed.project / "beats.json").read_bytes() == OLD


def test_a_valid_looking_candidate_from_a_child_that_exits_1_is_never_swapped(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path, exit_code=1)
    old_beats(bed)
    assert finish(bed, beats_body(redo=True)).state == "failed"
    assert entries(bed) == ["beats.json", "script.md"] and (bed.project / "beats.json").read_bytes() == OLD


def test_a_candidate_for_another_script_hash_fails_the_job_with_the_unreadable_message_and_the_old_beats_stay(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path, out=sidecar_bytes("f" * 64))
    old_beats(bed)
    final = finish(bed, beats_body(redo=True))
    assert (final.state, final.failure) == ("failed", BEATS_UNREADABLE)
    assert entries(bed) == ["beats.json", "script.md"] and (bed.project / "beats.json").read_bytes() == OLD


def test_a_first_run_that_finds_a_beats_json_made_by_hand_during_the_run_fails_and_keeps_that_file(stub_cli, tmp_path):
    release = tmp_path / "release"
    bed = beats_bed(stub_cli, tmp_path, wait_for_file=str(release))
    bed.post(beats_body())
    wait_until(lambda: bed.runner.current().state == "running" and any(CANDIDATE.fullmatch(n) for n in entries(bed)))
    old_beats(bed)
    release.write_text("go")
    final = wait_final(bed.runner)
    assert (final.state, final.failure) == ("failed", BEATS_EXIST)
    assert entries(bed) == ["beats.json", "script.md"] and (bed.project / "beats.json").read_bytes() == OLD


def test_a_cancel_mid_write_leaves_no_candidate_and_the_old_beats(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path, out=GOOD[:30], sleep=30, sigint="exit", sigint_exit_code=130)
    old_beats(bed)
    bed.post(beats_body(redo=True))
    wait_until(lambda: any(CANDIDATE.fullmatch(n) for n in entries(bed)))
    bed.runner.cancel()
    final = wait_final(bed.runner)
    assert final.state == "cancelled"
    assert entries(bed) == ["beats.json", "script.md"] and (bed.project / "beats.json").read_bytes() == OLD
    assert bed.launch_files() == [] and stat.S_ISREG(os.stat(bed.project / "beats.json").st_mode)


def test_a_start_names_the_candidate_after_the_job_has_a_free_slot_and_sweeps_a_leftover_first(stub_cli, tmp_path):
    bed = beats_bed(stub_cli, tmp_path)
    leftover = bed.project / ".write-beats-0123456789abcdef.tmp"
    leftover.write_bytes(b"half")
    kept = bed.project / ".write-restart-0123abcd-synth_record.json.tmp"
    kept.write_bytes(b"backup")
    bed.post(beats_body())
    wait_final(bed.runner)
    assert not leftover.exists() and kept.read_bytes() == b"backup"
