import threading

import pytest
from job_runner_helper import (
    Gate,
    RecordingObserver,
    make_runner,
    run_to_end,
    start_job,
    wait_final,
    wait_started,
    wait_until,
)


@pytest.mark.parametrize(
    ("spec", "on_success_calls"),
    [({}, 1), ({"exit_code": 3}, 0)],
)
def test_on_success_runs_only_after_a_clean_exit(stub_cli, tmp_path, spec, on_success_calls):
    calls: list[str] = []
    runner = make_runner(stub_cli(**spec), tmp_path)
    run_to_end(runner, on_success=lambda: calls.append("ok"))
    assert len(calls) == on_success_calls


def test_on_success_does_not_run_after_a_cancel(stub_cli, tmp_path):
    calls: list[str] = []
    stub = stub_cli(sigint="exit", sigint_exit_code=130, wait_for_file=str(tmp_path / "never"))
    runner = make_runner(stub, tmp_path)
    start_job(runner, on_success=lambda: calls.append("ok"))
    wait_started(stub)
    runner.cancel()
    assert wait_final(runner).state == "cancelled" and calls == []


def raising() -> None:
    raise RuntimeError("hook bug")


@pytest.mark.parametrize("hook", [lambda: "The pack could not be written.", raising])
def test_a_failing_on_success_turns_the_job_failed(stub_cli, tmp_path, hook):
    final = run_to_end(make_runner(stub_cli(), tmp_path), on_success=hook)
    assert (final.state, final.failure_kind) == ("failed", "other")
    assert final.failure


@pytest.mark.parametrize(
    ("spec", "outcome"),
    [({}, "done"), ({"exit_code": 3}, "failed")],
)
def test_on_finish_runs_once_with_the_outcome(stub_cli, tmp_path, spec, outcome):
    calls: list[tuple[str, int]] = []
    runner = make_runner(stub_cli(**spec), tmp_path)
    final = run_to_end(runner, on_finish=lambda result, scenes: calls.append((result, scenes)) or (None, None))
    assert calls == [(outcome, 0)] and final.state == outcome


def test_on_finish_runs_after_a_cancel_and_after_a_spawn_error(stub_cli, tmp_path):
    calls: list[str] = []

    def finish(outcome, scenes):
        calls.append(outcome)
        return None, None

    runner = make_runner(None, tmp_path, prefix=[str(tmp_path / "missing-program")])
    run_to_end(runner, on_finish=finish)
    stub = stub_cli(sigint="exit", sigint_exit_code=130, wait_for_file=str(tmp_path / "never"))
    runner = make_runner(stub, tmp_path)
    start_job(runner, on_finish=finish)
    wait_started(stub)
    runner.cancel()
    wait_final(runner)
    assert calls == ["failed", "cancelled"]


@pytest.mark.parametrize("emitted", [1])
def test_the_hook_sees_every_scene_done_even_when_the_child_exits_at_once(stub_cli, tmp_path, emitted):
    seen: list[int] = []
    runner = make_runner(stub_cli(stderr_lines=["scene done"] * emitted), tmp_path)
    run_to_end(
        runner, observer=RecordingObserver(runner), on_finish=lambda outcome, scenes: seen.append(scenes) or (None, None)
    )
    assert seen == [emitted] and runner.scenes_done() == emitted


def test_hooks_run_in_order_after_the_observer_flush_and_before_the_end(stub_cli, tmp_path):
    log: list[str] = []
    observer = RecordingObserver(log=log)

    def finish(outcome, scenes):
        log.append("on_finish")
        return None, None

    run_to_end(make_runner(stub_cli(), tmp_path), observer=observer, on_success=lambda: log.append("on_success"), on_finish=finish)
    assert log == ["flush", "on_success", "on_finish", "end"]


@pytest.mark.parametrize("how", ["done", "failed", "cancelled"])
def test_a_failure_message_from_on_finish_ends_the_job_failed_whatever_the_outcome_was(stub_cli, tmp_path, how):
    spec = {
        "done": {},
        "failed": {"exit_code": 3},
        "cancelled": {"sigint": "exit", "sigint_exit_code": 130, "wait_for_file": str(tmp_path / "never")},
    }[how]
    stub = stub_cli(**spec)
    runner = make_runner(stub, tmp_path)
    start_job(runner, on_finish=lambda result, scenes: ("The old copy could not be restored.", "note"))
    if how == "cancelled":
        wait_started(stub)
        runner.cancel()
    final = wait_final(runner)
    assert (final.state, final.failure_kind, final.failure, final.notice) == (
        "failed", "other", "The old copy could not be restored.", "note",
    )


def test_hooks_and_cleanup_finish_before_the_slot_is_released(stub_cli, tmp_path):
    gate = Gate((None, None))
    observer = RecordingObserver()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    runner = make_runner(stub_cli(), tmp_path)
    start_job(runner, on_finish=gate, observer=observer, cleanup=[scratch])
    assert gate.entered.wait(15)
    assert runner.reserve("synth", "p") is None
    assert runner.admit_zip() is None
    assert runner.job_active()
    assert runner.current().state == "running"
    assert observer.ends == []
    gate.open.set()
    assert wait_final(runner).state == "done"
    assert not scratch.exists()
    assert runner.reserve("synth", "p") is not None


def test_cancel_during_a_slow_hook_answers_without_a_signal_or_a_changed_outcome(stub_cli, tmp_path, killpgs):
    gate = Gate((None, None))
    runner = make_runner(stub_cli(), tmp_path)
    start_job(runner, on_finish=gate)
    assert gate.entered.wait(15)
    sent = list(killpgs)
    assert sent  # positive control: the recorder saw the exit sweep
    runner.cancel()
    runner.cancel()
    assert killpgs == sent
    assert runner.current().state == "running"
    gate.open.set()
    assert wait_final(runner).state == "done"


def test_a_cancelled_job_stays_cancelling_while_its_hook_runs(stub_cli, tmp_path):
    gate = Gate((None, None))
    stub = stub_cli(sigint="exit", sigint_exit_code=130, wait_for_file=str(tmp_path / "never"))
    runner = make_runner(stub, tmp_path)
    start_job(runner, on_finish=gate)
    wait_started(stub)
    runner.cancel()
    assert gate.entered.wait(15)
    runner.cancel()
    assert runner.current().state == "cancelling"
    gate.open.set()
    assert wait_final(runner).state == "cancelled"


def test_shutdown_waits_for_a_slow_hook(stub_cli, tmp_path):
    gate = Gate((None, None))
    runner = make_runner(stub_cli(), tmp_path)
    start_job(runner, on_finish=gate)
    assert gate.entered.wait(15)
    returned = threading.Event()
    threading.Thread(target=lambda: (runner.shutdown(), returned.set()), daemon=True).start()
    wait_until(lambda: runner.busy_reason() == "stopping")
    assert not returned.wait(0.3)
    gate.open.set()
    assert returned.wait(15)
    assert runner.current().state == "done"
