import io
import json
import os
import sys
import threading
import zipfile

import pytest
from job_runner_helper import (
    Gate,
    make_runner,
    start_job,
    wait_final,
    wait_started,
    wait_until,
)
from web_http_helper import make_request

from scenevoice.web import JobRunner, get_pack_zip
from scenevoice.web.workspace_error import NothingPackedError, PackTooLargeError


@pytest.fixture
def project(tmp_path):
    directory = tmp_path.resolve() / "ws" / "my-video"
    (directory / "audio").mkdir(parents=True)
    (directory / "scene_manifest.csv").write_bytes(b"manifest")
    (directory / "audio" / "001.wav").write_bytes(b"wav")
    return directory


def ask(project, project_id="my-video", **options):
    handler = get_pack_zip(lambda: project.parent, project_id, options.pop("key_file", None), JobRunner(cwd=project.parent, env={}), **options)
    return handler(make_request("GET", f"/api/projects/{project_id}/pack.zip"))


def kind(response):
    error = json.loads(response.body)["error"]
    return (response.status, error["kind"], error["message"])


def snapshot(directory):
    return sorted((str(path), path.stat().st_mtime_ns) for path in directory.rglob("*"))


def test_the_pack_is_a_200_zip_attachment_named_for_the_id_and_the_request_writes_nothing(project):
    before = snapshot(project.parent)
    response = ask(project)
    assert response.status == 200
    assert response.headers == (
        ("Content-Type", "application/zip"),
        ("Content-Disposition", 'attachment; filename="my-video.zip"'),
    )
    assert response.no_store is True
    assert zipfile.ZipFile(io.BytesIO(response.body)).namelist() == ["my-video/audio/001.wav", "my-video/scene_manifest.csv"]
    assert snapshot(project.parent) == before
    assert sorted(os.listdir(project)) == ["audio", "scene_manifest.csv"]


def test_a_missing_manifest_is_a_404_saying_nothing_has_been_packed(project):
    (project / "scene_manifest.csv").unlink()
    assert kind(ask(project)) == (404, "not_found", "Nothing has been packed yet.")


def test_a_total_over_the_cap_is_a_413_pointing_to_show_in_finder(project):
    response = ask(project, cap=5)
    status, error_kind, message = kind(response)
    assert (status, error_kind) == (413, "bad_request")
    assert "Show in Finder" in message and "1 GiB" in message
    assert response.no_store is True


def test_a_missing_project_and_an_invalid_id_are_404(project):
    assert kind(ask(project, "other"))[:2] == (404, "not_found")
    assert kind(ask(project, "My Video"))[:2] == (404, "not_found")


# Busy gate and admission (J2b): refused while a job holds the slot, and assembly holds a zip admission.
def ask_with(project, runner, project_id="my-video"):
    handler = get_pack_zip(lambda: project.parent, project_id, None, runner)
    return handler(make_request("GET", f"/api/projects/{project_id}/pack.zip"))


def reads_nothing(monkeypatch):
    calls = []
    module = sys.modules["scenevoice.web.get_pack_zip"]
    real = module.build_pack_zip
    monkeypatch.setattr(module, "build_pack_zip", lambda *a, **k: calls.append("built") or real(*a, **k))
    return calls


@pytest.mark.parametrize(
    ("kind_", "message"),
    [("synth", "SceneVoice is busy voicing."), ("align", "SceneVoice is busy updating line markers.")],
)
def test_a_download_while_the_slot_is_held_is_409_busy_with_the_running_kinds_message_and_assembly_never_begins(
    project, monkeypatch, kind_, message
):
    runner = JobRunner(cwd=project.parent, env={})
    assert runner.reserve(kind_, "other") is not None  # a `starting` slot refuses too, and in every project
    built = reads_nothing(monkeypatch)
    response = ask_with(project, runner)
    assert kind(response) == (409, "busy", message) and built == []


def test_a_download_while_the_server_stops_is_409_busy_stopping(project):
    runner = JobRunner(cwd=project.parent, env={})
    runner.shutdown()
    assert kind(ask_with(project, runner)) == (409, "busy", "SceneVoice is stopping.")


def test_the_busy_gate_comes_after_the_project_checks(project):
    runner = JobRunner(cwd=project.parent, env={})
    assert runner.reserve("synth", "p") is not None
    assert kind(ask_with(project, runner, "other"))[:2] == (404, "not_found")


def test_assembly_holds_a_zip_admission_that_is_gone_when_the_response_is_returned(project, monkeypatch):
    runner = JobRunner(cwd=project.parent, env={})
    seen = []
    module = sys.modules["scenevoice.web.get_pack_zip"]
    real = module.build_pack_zip

    def watching(*args, **kwargs):
        seen.append((runner.busy_reason(), runner.job_active()))
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "build_pack_zip", watching)
    assert ask_with(project, runner).status == 200
    assert seen == [("download", False)]  # an admission is not a job
    assert runner.busy_reason() is None and runner.reserve("synth", "my-video") is not None


@pytest.mark.parametrize("failure", [NothingPackedError, PackTooLargeError, RuntimeError])
def test_the_admission_is_released_when_assembly_raises_or_refuses(project, monkeypatch, failure):
    runner = JobRunner(cwd=project.parent, env={})

    def failing(*args, **kwargs):
        raise failure()

    monkeypatch.setattr(sys.modules["scenevoice.web.get_pack_zip"], "build_pack_zip", failing)
    try:
        ask_with(project, runner)
    except RuntimeError:
        assert failure is RuntimeError
    assert runner.busy_reason() is None and runner.reserve("synth", "my-video") is not None


def test_no_admission_is_taken_for_a_missing_project(project):
    runner = JobRunner(cwd=project.parent, env={})
    taken = []
    real = runner.admit_zip
    runner.admit_zip = lambda: taken.append(1) or real()  # type: ignore[method-assign]
    assert kind(ask_with(project, runner, "other"))[:2] == (404, "not_found")
    assert taken == []


def test_an_admission_blocks_reserve_and_reports_download_but_is_not_a_job(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path)
    admission = runner.admit_zip()
    assert admission is not None
    before = runner.current()
    assert runner.reserve("synth", "p") is None
    assert runner.busy_reason() == "download"
    assert runner.job_active() is False
    assert runner.current() == before  # an admission changes nothing the job status shows
    runner.release_zip(admission)
    assert runner.busy_reason() is None
    assert runner.reserve("synth", "p") is not None


def test_two_admissions_coexist_and_release_is_idempotent(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path)
    first, second = runner.admit_zip(), runner.admit_zip()
    assert first is not None and second is not None
    runner.release_zip(first)
    runner.release_zip(first)  # a second release of the same admission must not free the other one
    assert runner.reserve("synth", "p") is None and runner.busy_reason() == "download"
    runner.release_zip(second)
    assert runner.reserve("synth", "p") is not None


@pytest.mark.parametrize("phase", ["reserved", "running", "cancelling", "hooks"])
def test_no_zip_is_admitted_while_a_job_holds_the_slot(stub_cli, tmp_path, phase):
    gate = Gate((None, None))
    hold = tmp_path / "hold"
    spec = {"sigint": "ignore", "wait_for_file": str(hold)} if phase in ("running", "cancelling") else {}
    stub = stub_cli(**spec)
    runner = make_runner(stub, tmp_path)
    if phase == "reserved":
        assert runner.reserve("synth", "p") is not None
    else:
        start_job(runner, on_finish=gate)
        if phase == "hooks":
            assert gate.entered.wait(15)
        else:
            wait_started(stub)
        if phase == "cancelling":
            runner.cancel()
            assert runner.current().state == "cancelling"
    assert runner.admit_zip() is None
    assert runner.job_active() is True
    hold.write_text("go")
    gate.open.set()
    if phase != "reserved":
        wait_final(runner)
        assert runner.admit_zip() is not None


def race(runner) -> tuple[object, object]:
    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def reserve() -> None:
        barrier.wait()
        results["handle"] = runner.reserve("synth", "p")

    def zip_in() -> None:
        barrier.wait()
        results["zip"] = runner.admit_zip()

    threads = [threading.Thread(target=reserve), threading.Thread(target=zip_in)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    return results["handle"], results["zip"]


def test_a_zip_and_a_reservation_racing_for_the_slot_never_both_win(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path)
    for _ in range(25):
        handle, admission = race(runner)
        assert (handle is None) != (admission is None)
        if handle is not None:
            runner.release(handle)
        else:
            runner.release_zip(admission)


def test_shutdown_closes_admission_and_waits_for_a_held_one(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path)
    admission = runner.admit_zip()
    returned = threading.Event()
    threading.Thread(target=lambda: (runner.shutdown(), returned.set()), daemon=True).start()
    wait_until(lambda: runner.busy_reason() == "stopping")
    assert runner.admit_zip() is None
    assert not returned.wait(0.3)
    runner.release_zip(admission)
    assert returned.wait(10)


def test_shutdown_returns_at_the_bound_when_an_admission_is_never_released(stub_cli, tmp_path):
    runner = make_runner(stub_cli(), tmp_path, shutdown_bound=0.3)
    assert runner.admit_zip() is not None
    returned = threading.Event()
    threading.Thread(target=lambda: (runner.shutdown(), returned.set()), daemon=True).start()
    assert returned.wait(10)
