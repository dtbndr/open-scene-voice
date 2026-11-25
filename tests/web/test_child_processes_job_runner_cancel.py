import os
import sys

import pytest
from job_runner_helper import (
    RecordingObserver,
    make_runner,
    pid_gone,
    run_to_end,
    start_job,
    wait_final,
    wait_started,
    wait_until,
)

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.web import absolute_keys_file, child_env


def test_cancel_interrupts_the_group_and_the_job_ends_cancelled(stub_cli, tmp_path, killpgs):
    stub = stub_cli(sigint="exit", sigint_exit_code=130, wait_for_file=str(tmp_path / "never"))
    runner = make_runner(stub, tmp_path)
    start_job(runner)
    wait_started(stub)
    runner.cancel()
    assert runner.current().state == "cancelling"
    final = wait_final(runner)
    assert (final.state, final.failure) == ("cancelled", None)
    assert killpgs[0] == (stub.recording()["pgid"], 2)  # SIGINT to the child's own group first


def test_a_child_that_ignores_interrupt_and_its_grandchild_are_killed_after_the_delay(stub_cli, tmp_path):
    marker = tmp_path / "sigint-marker"
    grandchild = tmp_path / "grandchild.pid"
    stub = stub_cli(sigint="ignore", sigint_marker=str(marker), spawn_grandchild=str(grandchild), wait_for_file=str(tmp_path / "never"))
    runner = make_runner(stub, tmp_path)
    start_job(runner)
    wait_started(stub)
    runner.cancel()
    assert wait_final(runner).state == "cancelled"
    assert marker.read_text() == "sigint\n"  # it did receive the interrupt and ignored it
    assert pid_gone(stub.recording()["pid"])
    wait_until(lambda: pid_gone(int(grandchild.read_text())))


def test_a_grandchild_that_outlives_its_interrupted_parent_is_swept(stub_cli, tmp_path):
    grandchild = tmp_path / "grandchild.pid"
    stub = stub_cli(sigint="exit", spawn_grandchild=str(grandchild), wait_for_file=str(tmp_path / "never"))
    runner = make_runner(stub, tmp_path)
    start_job(runner)
    wait_started(stub)
    runner.cancel()
    wait_final(runner)
    wait_until(lambda: pid_gone(int(grandchild.read_text())))


def test_cancel_after_the_child_exited_sends_nothing(stub_cli, tmp_path, killpgs):
    runner = make_runner(stub_cli(), tmp_path)
    run_to_end(runner)
    sent = list(killpgs)
    assert sent  # positive control: the recorder sees the runner's group signals (the sweep at exit)
    runner.cancel()
    runner.cancel()
    assert killpgs == sent


@pytest.mark.parametrize(("exit_code", "state"), [(0, "done"), (130, "cancelled")])
def test_the_exit_code_after_a_cancel_request_decides_done_or_cancelled(stub_cli, tmp_path, exit_code, state):
    stub = stub_cli(sigint="exit", sigint_exit_code=exit_code, wait_for_file=str(tmp_path / "never"))
    runner = make_runner(stub, tmp_path)
    start_job(runner)
    wait_started(stub)
    runner.cancel()
    runner.cancel()  # idempotent
    assert wait_final(runner).state == state


@pytest.mark.parametrize(
    ("runs", "per_run", "state", "scenes_done"),
    [
        ([["a", "1"], ["a", "2"]], {"2": {"sigint": "exit", "sigint_exit_code": 130, "wait_for_file": "NEVER"}}, "cancelled", 1),
        ([["a", "1"], ["a", "2"]], {"1": {"sigint": "exit", "sigint_exit_code": 0, "wait_for_file": "NEVER"}}, "cancelled", 1),
        ([["a", "1"], ["a", "2"]], {"2": {"sigint": "exit", "sigint_exit_code": 0, "wait_for_file": "NEVER"}}, "done", 2),
    ],
)
def test_a_multi_run_cancel_stops_before_the_next_run_and_counts_completed_runs(
    stub_cli, tmp_path, runs, per_run, state, scenes_done
):
    never = str(tmp_path / "never")
    by_verb = {verb: {**fields, "wait_for_file": never} for verb, fields in per_run.items()}
    stub = stub_cli(by_verb=by_verb)
    runner = make_runner(stub, tmp_path)
    start_job(runner, runs=runs, total=2)
    cancelled_run = int(next(iter(per_run)))
    wait_started(stub, cancelled_run)
    runner.cancel()
    final = wait_final(runner)
    assert (final.state, final.scenes_done) == (state, scenes_done)
    assert len(stub.calls()) == (1 if per_run.get("1") else 2)


def test_the_observer_gets_the_end_event_once(stub_cli, tmp_path):
    observer = RecordingObserver()
    stub = stub_cli(sigint="exit", sigint_exit_code=130, wait_for_file=str(tmp_path / "never"))
    runner = make_runner(stub, tmp_path)
    start_job(runner, observer=observer)
    wait_started(stub)
    runner.cancel()
    wait_final(runner)
    wait_until(lambda: len(observer.ends) == 1)
    assert observer.ends[0].state == "cancelled"


def test_the_slot_is_exclusive_while_running_and_free_after_the_job(stub_cli, tmp_path):
    hold = tmp_path / "hold"
    stub = stub_cli(wait_for_file=str(hold))
    runner = make_runner(stub, tmp_path)
    start_job(runner, kind="synth", project="p", mode="all", total=4, scene=2)
    wait_started(stub)
    running = runner.current()
    assert (running.state, running.kind, running.project, running.mode, running.scene, running.total) == (
        "running", "synth", "p", "all", 2, 4,
    )
    assert runner.reserve("pack", "p") is None and runner.busy_reason() == "synth" and runner.job_active()
    hold.write_text("go")
    assert wait_final(runner).state == "done"
    assert not runner.job_active() and runner.busy_reason() is None
    assert runner.reserve("pack", "p") is not None


@pytest.mark.parametrize(
    ("spec", "state"),
    [({"exit_code": 0}, "done"), ({"exit_code": 3}, "failed")],
)
def test_the_slot_is_released_after_each_outcome(stub_cli, tmp_path, spec, state):
    runner = make_runner(stub_cli(**spec), tmp_path)
    final = run_to_end(runner)
    assert final.state == state
    assert (final.failure_kind, final.failure is None) == (("other", False) if state == "failed" else (None, True))
    assert runner.reserve("synth", "p") is not None


def test_a_spawn_error_ends_failed_and_releases_the_slot(tmp_path):
    runner = make_runner(None, tmp_path, prefix=[str(tmp_path / "missing-program")])
    final = run_to_end(runner)
    assert (final.state, final.failure_kind) == ("failed", "other")
    assert final.failure
    assert runner.reserve("synth", "p") is not None


def test_runs_go_in_order_and_stop_at_the_first_failure(stub_cli, tmp_path):
    stub = stub_cli(by_verb={"2": {"exit_code": 2}})
    runner = make_runner(stub, tmp_path)
    final = run_to_end(runner, runs=[["synth", "1"], ["synth", "2"], ["synth", "3"]], total=3)
    assert [call["argv"] for call in stub.calls()] == [["synth", "1"], ["synth", "2"]]
    assert (final.state, final.scenes_done, final.total) == ("failed", 1, 3)


def test_a_multi_run_job_is_done_only_when_every_run_completed(stub_cli, tmp_path):
    stub = stub_cli()
    final = run_to_end(make_runner(stub, tmp_path), runs=[["synth", "1"], ["synth", "2"], ["synth", "3"]], total=3)
    assert (final.state, final.scenes_done) == ("done", 3)
    assert len(stub.calls()) == 3


def test_the_child_runs_in_the_launch_dir_as_a_group_leader_with_no_stdin_and_a_clean_environment(
    stub_cli, tmp_path, monkeypatch
):
    stub = stub_cli()
    environ = {name: "secret-value" for name in KEY_NAMES} | {"HOME": "/h", "SCENEVOICE_KEYS_FILE": "rel/keys.env"}
    monkeypatch.chdir(tmp_path)
    runner = make_runner(stub, tmp_path, env=child_env(absolute_keys_file(environ)))
    run_to_end(runner)
    recording = stub.recording()
    assert recording["cwd"] == str((tmp_path / "launch").resolve())
    assert recording["stdin"] == b""
    assert recording["pgid"] == recording["pid"] != os.getpgrp()
    assert all(recording["env"][name] is None for name in KEY_NAMES)
    assert recording["env"]["SCENEVOICE_KEYS_FILE"] == str(tmp_path / "rel" / "keys.env")
    assert recording["argv"] == ["synth", "1"]


def test_the_runner_prepends_the_cli_prefix_by_default(stub_cli, tmp_path, monkeypatch):
    stub = stub_cli()
    monkeypatch.setattr(sys.modules["scenevoice.web.job_runner"], "cli_argv_prefix", lambda: stub.prefix)
    run_to_end(make_runner(stub, tmp_path, prefix=None))
    assert stub.recording()["argv"] == ["synth", "1"]  # the stub ran, so the patched prefix was the one used


def test_two_streams_of_one_mib_finish_and_stdout_is_captured_bounded_and_counted(stub_cli, tmp_path):
    mib = 1024 * 1024
    observer = RecordingObserver()
    runner = make_runner(stub_cli(flood_stdout=mib, flood_stderr=mib), tmp_path)
    final = run_to_end(runner, observer=observer)
    assert final.state == "done"
    capture = runner.stdout()
    assert (len(capture.data), capture.total) == (256 * 1024, mib)
    assert len(observer.lines) == 1024


def test_stderr_lines_reach_the_observer_while_the_child_is_still_running(stub_cli, tmp_path):
    observer = RecordingObserver()
    runner = make_runner(stub_cli(stderr_lines=["first", "second"], stderr_delay=0.3), tmp_path)
    start_job(runner, observer=observer)
    wait_until(lambda: observer.lines == ["first"])
    assert runner.current().state == "running"
    assert wait_final(runner).state == "done"
    assert observer.lines == ["first", "second"]
    assert observer.flushes == 1 and [status.state for status in observer.ends] == ["done"]


def test_stdout_of_the_last_run_is_kept(stub_cli, tmp_path):
    runner = make_runner(stub_cli(stdout="hello"), tmp_path)
    run_to_end(runner)
    assert runner.stdout().data == b"hello"


@pytest.mark.parametrize("outcome", ["done", "failed", "spawn"])
def test_cleanup_paths_are_deleted_in_every_outcome(stub_cli, tmp_path, outcome):
    folder = tmp_path / "scratch"
    (folder / "inner").mkdir(parents=True)
    (folder / "inner" / "file").write_text("x")
    single = tmp_path / "single.txt"
    single.write_text("x")
    options = {"prefix": [str(tmp_path / "missing-program")]} if outcome == "spawn" else {}
    runner = make_runner(stub_cli(exit_code=0 if outcome == "done" else 3), tmp_path, **options)
    run_to_end(runner, cleanup=[folder, single, tmp_path / "never-existed"])
    assert not folder.exists() and not single.exists()


def test_cancel_run_of_a_finished_run_refuses_and_leaves_the_next_run_untouched(stub_cli, tmp_path, killpgs):
    """WS47-01, P1 quota: a Cancel naming run A must never stop project B's paid run."""
    gate = tmp_path / "gate"
    gate.write_text("go")
    stub = stub_cli(sigint="exit", sigint_exit_code=130, wait_for_file=str(gate))
    runner = make_runner(stub, tmp_path)
    first = run_to_end(runner).run
    assert first is not None and len(first) == 32
    gate.unlink()
    start_job(runner)
    wait_started(stub, 2)
    second = runner.current().run
    assert second != first
    sent = list(killpgs)
    assert runner.cancel_run(first) == "stale"
    assert (runner.current().state, killpgs) == ("running", sent)
    assert runner.cancel_run(second) == "stopped"
    assert wait_final(runner).state == "cancelled"
    assert runner.cancel_run(second) == "nothing"
