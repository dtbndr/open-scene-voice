"""The zip admission guard (J2b) across both arrival orders: the zip handler against the start route, one job slot for both."""

import json
import sys
import threading
import zipfile
from io import BytesIO

import pytest
from job_runner_helper import Gate, start_job, wait_final, wait_started, wait_until
from post_job_helper import PLAN_JSON, SCRIPT, BlockingPlan, JobBed, synth_restart
from web_http_helper import make_request

from scenevoice.web import get_pack_zip, post_job, put_script
from scenevoice.web.request import Request

DOWNLOAD = "SceneVoice is busy preparing a download."
VOICING = "SceneVoice is busy voicing."


class Download:
    """The zip handler of project `p` over the bed's runner; the first assembly can be held on a barrier after the admission."""

    def __init__(self, bed, monkeypatch, hold_first=False):
        self.bed = bed
        self.entered = threading.Event()
        self.open = threading.Event()
        self.built = 0
        module = sys.modules["scenevoice.web.get_pack_zip"]
        real = module.build_pack_zip

        def build(*args, **kwargs):
            self.built += 1
            if hold_first and self.built == 1:
                self.entered.set()
                assert self.open.wait(15)
            return real(*args, **kwargs)

        monkeypatch.setattr(module, "build_pack_zip", build)
        self.handler = get_pack_zip(lambda: bed.workspace, "p", None, bed.runner)
        self.answers: list = []

    def get(self):
        return self.handler(make_request("GET", "/api/projects/p/pack.zip"))

    def get_in_thread(self):
        worker = threading.Thread(target=lambda: self.answers.append(self.get()))
        worker.start()
        return worker


def packed(bed):
    (bed.project / "scene_manifest.csv").write_bytes(b"manifest-1")
    (bed.project / "resolve_timeline.otio").write_bytes(b"timeline-1")


def error(response):
    body = json.loads(response.body)["error"]
    return response.status, body["kind"], body["message"]


@pytest.fixture
def bed(stub_cli, tmp_path):
    bed = JobBed(stub_cli(stdout=PLAN_JSON), tmp_path)
    bed.save_script()
    bed.voice()
    packed(bed)
    return bed


def other_project_start(bed):
    (bed.workspace / "q").mkdir()
    (bed.workspace / "q" / "script.md").write_bytes(SCRIPT)
    return post_job(bed.context, "q")


# --- a download is assembling when a start arrives ------------------------------------------------------------------


def test_a_start_while_a_download_assembles_is_409_busy_touches_nothing_and_succeeds_once_the_archive_is_whole(bed, monkeypatch):
    download = Download(bed, monkeypatch, hold_first=True)
    worker = download.get_in_thread()
    assert download.entered.wait(15)
    before = sorted(path.name for path in bed.project.rglob("*"))
    assert bed.error(synth_restart()) == (409, "busy", DOWNLOAD)
    refused_elsewhere = other_project_start(bed)(Request("POST", "/api/projects/q/jobs", json_body=synth_restart()))
    assert error(refused_elsewhere) == (409, "busy", DOWNLOAD)  # the guard is global, like the slot
    assert bed.run.calls == [] and bed.children() == [] and bed.launch_files() == []  # script.md never read, no child, no file
    assert sorted(path.name for path in bed.project.rglob("*")) == before
    download.open.set()
    worker.join(15)
    (response,) = download.answers
    names = zipfile.ZipFile(BytesIO(response.body)).namelist()
    assert response.status == 200 and "p/scene_manifest.csv" in names and "p/resolve_timeline.otio" in names
    assert bed.post(synth_restart())[0].status == 202
    wait_final(bed.runner)


def test_a_refused_start_does_not_clear_the_previous_jobs_last_result(bed, monkeypatch):
    assert bed.post(synth_restart())[0].status == 202
    last = wait_final(bed.runner)
    admission = bed.runner.admit_zip()
    assert admission is not None
    assert bed.error(synth_restart())[:2] == (409, "busy")
    assert bed.runner.current() == last
    bed.runner.release_zip(admission)


# --- a job holds the slot when a download arrives -------------------------------------------------------------------


def test_a_download_while_a_start_is_held_in_plan_is_409_busy_and_assembly_never_begins(stub_cli, tmp_path, monkeypatch):
    bed = JobBed(stub_cli(stdout=PLAN_JSON), tmp_path, run=BlockingPlan())
    bed.save_script()
    bed.voice()
    packed(bed)
    download = Download(bed, monkeypatch)
    starter = threading.Thread(target=lambda: bed.post(synth_restart()))
    starter.start()
    assert bed.run.entered.wait(15) and bed.runner.current().state == "starting"
    assert error(download.get()) == (409, "busy", VOICING) and download.built == 0
    bed.run.open.set()
    starter.join(15)
    wait_final(bed.runner)


@pytest.mark.parametrize("cancel", [False, True])
def test_a_download_while_a_job_runs_or_cancels_is_409_busy_and_assembly_never_begins(stub_cli, tmp_path, monkeypatch, cancel):
    hold = tmp_path / "hold"
    bed = JobBed(stub_cli(stdout=PLAN_JSON, sigint="ignore", wait_for_file=str(hold)), tmp_path)
    bed.save_script()
    bed.voice()
    packed(bed)
    download = Download(bed, monkeypatch)
    assert bed.post(synth_restart())[0].status == 202
    wait_started(bed.stub)
    if cancel:
        bed.runner.cancel()
        assert bed.runner.current().state == "cancelling"
    assert error(download.get()) == (409, "busy", VOICING) and download.built == 0
    hold.write_text("go")
    wait_final(bed.runner)


def test_a_pack_job_rewriting_the_outputs_cannot_interleave_with_assembly_so_archive_and_disk_agree_before_and_after(
    stub_cli, tmp_path, monkeypatch
):
    hold = tmp_path / "hold"
    bed = JobBed(stub_cli(stdout=PLAN_JSON, wait_for_file=str(hold)), tmp_path)
    bed.save_script()
    bed.voice()
    packed(bed)
    download = Download(bed, monkeypatch)
    before = zipfile.ZipFile(BytesIO(download.get().body))
    assert before.read("p/scene_manifest.csv") == b"manifest-1"
    assert bed.post({"kind": "pack"})[0].status == 202  # deletes the old outputs first, then the child runs
    wait_started(bed.stub)
    assert not (bed.project / "scene_manifest.csv").exists()
    assert error(download.get())[:2] == (409, "busy")  # the half-rewritten folder is never zipped
    hold.write_text("go")
    wait_final(bed.runner)
    assert error(download.get()) == (404, "not_found", "Nothing has been packed yet.")  # the disk has no manifest either


def test_a_download_during_a_slow_on_finish_is_409_busy_while_the_state_is_still_running(bed, monkeypatch):
    download = Download(bed, monkeypatch)
    gate = Gate((None, None))
    start_job(bed.runner, on_finish=gate)
    assert gate.entered.wait(15)
    assert bed.runner.current().state == "running"
    assert error(download.get()) == (409, "busy", VOICING)
    gate.open.set()
    wait_final(bed.runner)


# --- downloads coexist with each other and with saves ---------------------------------------------------------------


def test_while_a_download_assembles_a_save_and_a_second_download_both_succeed(bed, monkeypatch):
    download = Download(bed, monkeypatch, hold_first=True)
    worker = download.get_in_thread()
    assert download.entered.wait(15)
    save = put_script(lambda: bed.workspace, "p", None, bed.runner, bed.script_lock)
    saved = save(Request("PUT", "/api/projects/p/script", json_body={"text": "new"}))
    assert saved.status == 200
    assert download.get().status == 200  # the second download passes the first's held build, which waits only for its own barrier
    download.open.set()
    worker.join(15)
    wait_until(lambda: bed.runner.busy_reason() is None)
