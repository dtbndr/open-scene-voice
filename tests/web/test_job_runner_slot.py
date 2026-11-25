import threading
import time

import pytest
from job_runner_helper import (
    make_runner,
    run_to_end,
    wait_final,
    wait_started,
    wait_until,
)

from scenevoice.web import FIXED_FAILURE, JobEvents, JobSpec, SlotRefused


def spec(**fields):
    return JobSpec(**{"kind": "synth", "mode": "all", "project": "p", "runs": [["synth", "1"]], **fields})


def test_reserve_gives_a_handle_once_and_release_frees_the_slot(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path)
    handle = runner.reserve("synth", "p")
    assert handle is not None
    assert runner.reserve("synth", "q") is None
    runner.release(handle)
    assert runner.reserve("synth", "q") is not None


def test_a_reserved_slot_reports_starting_with_only_the_kind_and_project(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path)
    assert runner.current().state == "idle"
    assert runner.reserve("pack", "proj") is not None
    current = runner.current()
    assert (current.state, current.kind, current.project) == ("starting", "pack", "proj")
    assert (current.mode, current.scene, current.total, current.scenes_done) == (None, None, 0, 0)
    assert (current.failure, current.failure_kind, current.notice) == (None, None, None)
    assert runner.job_active() and runner.busy_reason() == "pack"


def test_release_is_idempotent_and_a_noop_after_start(stub_cli, tmp_path):
    hold = tmp_path / "hold"
    stub = stub_cli(wait_for_file=str(hold))
    runner = make_runner(stub, tmp_path)
    first = runner.reserve("synth", "p")
    runner.release(first)
    runner.release(first)
    second = runner.reserve("synth", "p")
    assert second is not None  # the second release of the first handle did not free the new reservation
    runner.release(first)
    assert runner.reserve("synth", "p") is None
    runner.start(second, spec())
    wait_started(stub)
    runner.release(second)
    assert runner.reserve("synth", "p") is None  # release after start does nothing: the job still owns the slot
    hold.write_text("go")
    assert wait_final(runner).state == "done"



@pytest.mark.parametrize("how", ["released", "cancelled", "closed", "started"])
def test_start_refuses_a_handle_that_is_no_longer_usable(stub_cli, tmp_path, how):
    stub = stub_cli()
    runner = make_runner(stub, tmp_path)
    handle = runner.reserve("synth", "p")
    if how == "released":
        runner.release(handle)
    elif how == "cancelled":
        runner.cancel()
    elif how == "closed":
        threading.Thread(target=runner.shutdown, daemon=True).start()
        wait_until(lambda: runner.busy_reason() == "stopping")
    else:
        runner.start(handle, spec())
        wait_final(runner)
    with pytest.raises(SlotRefused):
        runner.start(handle, spec())
    assert len(stub.calls()) == (1 if how == "started" else 0)


def test_cancel_on_a_reserved_slot_keeps_it_held_until_the_owner_releases(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path)
    handle = runner.reserve("synth", "p")
    runner.cancel()
    assert runner.current().state == "cancelling"
    assert runner.reserve("synth", "p") is None
    runner.release(handle)
    assert runner.current().state == "idle"
    assert runner.reserve("synth", "p") is not None


def test_shutdown_during_planning_refuses_the_start_spawns_nothing_and_ends_idle(stub_cli, tmp_path):
    stub = stub_cli()
    runner = make_runner(stub, tmp_path)
    handle = runner.reserve("synth", "p")
    returned = threading.Event()

    def shut() -> None:
        runner.shutdown()
        returned.set()

    thread = threading.Thread(target=shut, daemon=True)
    thread.start()
    wait_until(lambda: runner.busy_reason() == "stopping")
    assert not returned.is_set()  # still waiting for the owner's release
    with pytest.raises(SlotRefused):
        runner.start(handle, spec())
    runner.release(handle)
    assert returned.wait(10)
    assert runner.current().state == "idle"
    assert runner.reserve("synth", "p") is None
    assert stub.calls() == []


def test_shutdown_returns_at_the_bound_when_a_handle_is_never_released(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path, shutdown_bound=0.3)
    assert runner.reserve("synth", "p") is not None
    began = time.monotonic()
    runner.shutdown()
    assert time.monotonic() - began >= 0.25


def test_a_reservation_that_never_starts_gives_back_the_previous_jobs_last_result(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path)
    for _ in range(2):  # the second round has a finished job behind it too
        runner.start(runner.reserve("synth", "p") or pytest.fail("slot"), spec())
        finished = wait_final(runner)
        handle = runner.reserve("synth-scene", "q")
        assert handle is not None and runner.current().state == "starting"
        handle.refused = True  # a cancel before start does not change what release gives back
        runner.release(handle)
        assert runner.current() == finished and finished.state == "done"


@pytest.mark.parametrize("how", ["reserved", "released", "cancelled", "closed", "started"])
def test_valid_says_whether_a_handle_can_still_start(stub_cli, tmp_path, how):
    runner = make_runner(stub_cli(), tmp_path, shutdown_bound=0.05)
    handle = runner.reserve("synth", "p")
    if how == "released":
        runner.release(handle)
    elif how == "cancelled":
        runner.cancel()
    elif how == "closed":
        runner.shutdown()
    elif how == "started":
        runner.start(handle, spec())
    assert runner.valid(handle) is (how == "reserved")
    wait_until(lambda: how != "started" or runner.current().state == "done")


def test_a_run_replaced_by_a_reservation_is_still_found_with_its_own_failure(stub_cli, tmp_path):
    """WS47-02, P1 quota: the page that started A learns A's own fate after B reserved the slot."""
    fail = '{"command": "synth", "event": "fail", "kind": "quota", "message": "raw", "scene": 1, "status": 429}'
    stub = stub_cli(exit_code=1, stderr_lines=[fail])
    runner = make_runner(stub, tmp_path)
    hub = JobEvents()
    observer = hub.observer(scrub=lambda text: text, on_scene_done=runner.note_scene_done)
    final = run_to_end(runner, observer=observer)
    assert runner.reserve("synth", "other") is not None  # B holds the slot; A is no longer current
    assert final.run is not None
    found = runner.lookup(final.run)
    assert found is not None and found[0].state == "failed"
    assert found[1] == {"kind": "quota", "message": FIXED_FAILURE, "scene": 1, "status": 429}
    assert runner.lookup("0" * 32) is None
