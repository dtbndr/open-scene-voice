from pathlib import Path

from detail_helper import plan_stdout, put_record, put_wavs
from job_runner_helper import wait_final
from post_job_helper import BODIES, SCRIPT, WAVS, align_body
from start_wiring_helper import running_start_server
from web_http_helper import parse_response

from scenevoice.web import build_align_argv, build_pack_argv


def voiced_project(server, tmp_path):
    server.send("POST", "/api/projects", {"name": "My Video"})
    server.send("PUT", "/api/projects/my-video/script", {"text": SCRIPT.decode("utf-8")})
    project = tmp_path / "ws" / "my-video"
    put_wavs(project, WAVS)
    put_record(project, BODIES, WAVS)
    return project


def test_align_over_http_runs_one_stub_call_with_the_align_argv(stub_cli, tmp_path, loopback_only):
    stub = stub_cli(stdout=plan_stdout(BODIES))
    with running_start_server(stub, tmp_path) as server:
        project = voiced_project(server, tmp_path)
        started = parse_response(server.send("POST", "/api/projects/my-video/jobs", align_body()))
        assert started.status == 202 and started.json()["job"]["kind"] == "align"
        assert wait_final(server.runner).state == "done"
        argv = stub.calls()[-1]["argv"]
        assert argv == build_align_argv(Path(argv[3]), project)


def test_pack_over_http_clears_the_old_outputs_and_runs_one_stub_call_with_the_pack_argv(stub_cli, tmp_path, loopback_only):
    stub = stub_cli(stdout=plan_stdout(BODIES))
    with running_start_server(stub, tmp_path) as server:
        project = voiced_project(server, tmp_path)
        (project / "scene_manifest.csv").write_bytes(b"old")
        started = parse_response(server.send("POST", "/api/projects/my-video/jobs", {"kind": "pack"}))
        assert started.status == 202 and started.json()["job"]["kind"] == "pack"
        assert wait_final(server.runner).state == "done"
        argv = stub.calls()[-1]["argv"]
        assert argv == build_pack_argv(Path(argv[5]), project) and not (project / "scene_manifest.csv").exists()


def test_the_busy_gate_over_http_one_slot_refuses_a_pack_start_during_a_download_and_a_save_and_a_download_during_a_job(
    stub_cli, tmp_path, loopback_only
):
    stub = stub_cli(stdout=plan_stdout(BODIES))
    with running_start_server(stub, tmp_path) as server:
        project = voiced_project(server, tmp_path)
        (project / "scene_manifest.csv").write_bytes(b"manifest")

        def answer(method, path, body=None):
            parsed = parse_response(server.send(method, path, body))
            return parsed.status, (parsed.json()["error"]["message"] if parsed.status == 409 else None)

        admission = server.runner.admit_zip()
        assert admission is not None  # a download being assembled
        assert answer("POST", "/api/projects/my-video/jobs", {"kind": "pack"}) == (409, "SceneVoice is busy preparing a download.")
        assert (project / "scene_manifest.csv").exists()  # the pack start deleted nothing
        server.runner.release_zip(admission)
        handle = server.runner.reserve("synth", "my-video")  # a start held before its child
        assert handle is not None
        busy = "SceneVoice is busy voicing."
        assert answer("PUT", "/api/projects/my-video/script", {"text": "x"}) == (409, busy)
        assert answer("GET", "/api/projects/my-video/pack.zip") == (409, busy)
        server.runner.release(handle)
        assert answer("PUT", "/api/projects/my-video/script", {"text": SCRIPT.decode("utf-8")})[0] == 200
        assert answer("GET", "/api/projects/my-video/pack.zip")[0] == 200
