import functools
import json
import sys
from pathlib import Path

from beats_sidecar_helper import sidecar_bytes
from detail_helper import plan_stdout, put_record, put_wavs, sha
from job_events_helper import parse_sse
from job_runner_helper import wait_final, wait_until
from job_wiring_helper import running_jobs_server
from post_job_helper import (
    BEATS_MODEL,
    BODIES,
    BODIES3,
    MODEL,
    PLAN_JSON,
    SCRIPT,
    SCRIPT3,
    WAVS,
    beats_body,
    confirm_for,
    synth_all,
    synth_rest,
    synth_restart,
)
from restart_helper import old_generation, snapshot
from start_wiring_helper import running_start_server
from web_http_helper import parse_response

from scenevoice.web import (
    FIXED_FAILURE,
    JobEvents,
    build_beats_argv,
    build_synth_argv,
    scrub_text,
)


def event(**fields: object) -> str:
    return json.dumps({"command": "synth", **fields})


def scene(number: int, state: str) -> str:
    return event(event="scene", message=f"scene {number}", state=state, scene=number, total=2)


def test_events_arrive_live_and_a_second_connection_with_last_event_id_resumes(stub_cli, tmp_path, loopback_only) -> None:
    gate = tmp_path / "go"
    stub = stub_cli(
        wait_for_file=str(gate),
        stderr_lines=[scene(1, "started"), scene(1, "done"), event(event="note", message="almost")],
    )
    with running_jobs_server(stub, tmp_path) as server:
        server.start()
        wait_until(lambda: server.runner.current().state == "running")
        client = server.open_events()
        head = server.read_until(client, b"\n\n")
        assert b"200" in head.split(b"\r\n", 1)[0]
        gate.write_text("go", encoding="utf-8")
        parsed = server.read_to_close(client, head)
        assert parsed.one("Content-Type") == "text/event-stream; charset=utf-8"
        assert parsed.one("Cache-Control") == "no-store"
        assert "content-length" not in parsed.headers
        ids = [identifier for identifier, _ in parse_sse(parsed.body)]
        assert ids == ["0-1", "1-1", "1-2", "1-3", "1-4"]
        assert server.current()["state"] == "done"
        _, resumed = server.stream("1-2")
        assert [identifier for identifier, _ in resumed] == ["0-1", "1-3", "1-4"]
        assert resumed[-1][1]["type"] == "end" and resumed[-1][1]["state"] == "done"
        again, _ = server.stream("1-4")
        assert (again.status, again.body) == (204, b"")


def test_a_client_that_disconnects_mid_run_does_not_end_the_job(stub_cli, tmp_path, loopback_only, capsys) -> None:
    gate = tmp_path / "go"
    stub = stub_cli(wait_for_file=str(gate), stderr_lines=[scene(1, "done")])
    with running_jobs_server(stub, tmp_path) as server:
        server.start()
        wait_until(lambda: server.runner.current().state == "running")
        client = server.open_events()
        server.read_until(client, b"\n\n")
        client.close()
        gate.write_text("go", encoding="utf-8")
        assert wait_final(server.runner).state == "done"
        _, replay = server.stream()
        assert [event["type"] for _, event in replay] == ["state", "scene", "end"]
        assert replay[-1][1]["state"] == "done"
        assert capsys.readouterr().err == ""


def test_cancel_over_http_ends_the_job_cancelled_after_the_child_exits(stub_cli, tmp_path, loopback_only) -> None:
    stub = stub_cli(sigint="exit", sigint_exit_code=130, wait_for_file=str(tmp_path / "never"))
    with running_jobs_server(stub, tmp_path) as server:
        server.start()
        wait_until(lambda: any(call["event"] == "start" for call in stub.events()))
        client = server.open_events()
        head = server.read_until(client, b"\n\n")
        run = server.current()["job"]["run"]
        cancelled = parse_response(server.send("POST", "/api/jobs/current/cancel", {"run": run}))
        assert (cancelled.status, cancelled.json()) == (200, {"cancelling": True})
        parsed = server.read_to_close(client, head)
        last = parse_sse(parsed.body)[-1]
        assert last[1]["type"] == "end" and last[1]["state"] == "cancelled"
        nothing = parse_response(server.send("POST", "/api/jobs/current/cancel", {"run": run}))
        assert (nothing.status, nothing.json()["error"]["kind"]) == (404, "not_found")


def test_a_traceback_on_the_childs_stderr_appears_in_no_event(stub_cli, tmp_path, loopback_only) -> None:
    secret = "/Users/someone/secret-project"
    stub = stub_cli(
        exit_code=1,
        stderr_lines=[
            scene(1, "started"),
            "Traceback (most recent call last):",
            f'  File "{secret}/app.py", line 3, in <module>',
            "RuntimeError: boom",
            "usage: scenevoice synth [-h]",
            event(event="fail", message=f"raw provider text {secret}", kind="quota", scene=1, line=None, status=429),
        ],
    )
    with running_jobs_server(stub, tmp_path) as server:
        scrub = functools.partial(
            scrub_text, project_dir=None, project_id=None, launch_dir=tmp_path, workspace=Path(secret), key_file=None
        )
        server.start(scrub=scrub)
        wait_final(server.runner)
        parsed, events = server.stream()
        assert all(word not in parsed.body.decode() for word in ("Traceback", "RuntimeError", "usage:", secret))
        assert [event["type"] for _, event in events] == ["state", "scene", "fail", "end"]
        failure = events[-1][1]["job"]["failure"]
        assert failure == {"kind": "quota", "message": FIXED_FAILURE, "scene": 1, "status": 429}


def test_run_web_registers_the_job_routes_and_closes_the_events_after_the_runner(recorder, monkeypatch) -> None:
    module = sys.modules["scenevoice.web.run_web"]
    order: list[str] = []
    seen: dict[str, object] = {}

    class RecordingEvents(JobEvents):
        def close(self) -> None:
            order.append("events.close")
            super().close()

    real_make_server = module.make_server

    def make_server(sock, routes, gate, **options):
        seen["paths"] = [path for path in ("/api/jobs/current", "/api/jobs/current/events", "/api/jobs/current/cancel") if path in routes]
        return real_make_server(sock, routes, gate, **options)

    real_runner = module.JobRunner

    class RecordingRunner(real_runner):  # type: ignore[valid-type, misc]
        def shutdown(self) -> None:
            order.append("runner.shutdown")
            super().shutdown()

    monkeypatch.setattr(module, "JobEvents", RecordingEvents)
    monkeypatch.setattr(module, "make_server", make_server)
    monkeypatch.setattr(module, "JobRunner", RecordingRunner)

    def serve(server) -> None:
        raise KeyboardInterrupt

    assert recorder.run(serve=serve) == 0
    assert seen["paths"] == ["/api/jobs/current", "/api/jobs/current/events", "/api/jobs/current/cancel"]
    assert order == ["runner.shutdown", "events.close"]


def line(**fields: object) -> str:
    return json.dumps({"command": "synth", **fields})


def test_a_start_over_http_runs_the_child_with_the_pinned_argv_and_progress_arrives_on_the_events_stream(
    stub_cli, tmp_path, loopback_only
):
    project = tmp_path / "ws" / "my-video"
    stub = stub_cli(
        stdout=PLAN_JSON,
        stderr_lines=[
            line(event="scene", message=f"voicing {project}/audio/001.wav", state="started", scene=1, total=2),
            line(event="scene", message="done", state="done", scene=1, total=2),
            line(event="scene", message="done", state="done", scene=2, total=2),
        ],
    )
    with running_start_server(stub, tmp_path) as server:
        server.send("POST", "/api/projects", {"name": "My Video"})
        server.send("PUT", "/api/projects/my-video/script", {"text": SCRIPT.decode("utf-8")})
        body = synth_all(confirm=confirm_for(SCRIPT))
        assert sha(SCRIPT) == body["confirm"]["revision"]
        refused = parse_response(server.send("POST", "/api/projects/my-video/jobs", body, cookie=False))
        assert (refused.status, refused.json()["error"]["kind"]) == (401, "stale_link")
        started = parse_response(server.send("POST", "/api/projects/my-video/jobs", body))
        assert started.status == 202 and started.json()["job"]["kind"] == "synth"
        assert wait_final(server.runner).state == "done"
        synth = stub.calls()[-1]["argv"]
        assert synth == build_synth_argv(
            Path(synth[1]), project, voice="Leda", model=MODEL, language=None, instruction=None, scene=None
        )
        parsed, events = server.stream()
        assert [event["type"] for _, event in events] == ["state", "scene", "scene", "scene", "end"]
        assert events[1][1]["message"] == "voicing my-video/audio/001.wav"
        assert events[-1][1]["job"]["scenes_done"] == 2
        assert str(tmp_path) not in parsed.body.decode()


def make_project(server, tmp_path):
    server.send("POST", "/api/projects", {"name": "My Video"})
    server.send("PUT", "/api/projects/my-video/script", {"text": SCRIPT3.decode("utf-8")})
    return tmp_path / "ws" / "my-video"


def test_voice_the_rest_over_http_runs_one_stub_call_per_missing_scene_with_the_records_settings(stub_cli, tmp_path, loopback_only):
    stub = stub_cli(stdout=plan_stdout(BODIES3))
    with running_start_server(stub, tmp_path) as server:
        project = make_project(server, tmp_path)
        put_wavs(project, {1: WAVS[1]})
        put_record(project, BODIES3, {1: WAVS[1]})
        body = synth_rest(BODIES3[1:], confirm=confirm_for(SCRIPT3, BODIES3[1:]))
        started = parse_response(server.send("POST", "/api/projects/my-video/jobs", body))
        assert started.status == 202 and started.json()["job"]["mode"] == "rest"
        assert wait_final(server.runner).state == "done"
        calls = [call["argv"] for call in stub.calls()][-2:]
        assert calls == [
            build_synth_argv(Path(calls[0][1]), project, voice="Leda", model=MODEL, language="en-GB", instruction=None, scene=n)
            for n in (2, 3)
        ]


def test_start_again_over_http_sets_the_old_generation_aside_runs_a_full_synth_and_discards_it_on_success(stub_cli, tmp_path, loopback_only):
    stub = stub_cli(stdout=plan_stdout(BODIES3))
    with running_start_server(stub, tmp_path) as server:
        project = make_project(server, tmp_path)
        old = old_generation(project)
        body = synth_restart(confirm=confirm_for(SCRIPT3, BODIES3))
        started = parse_response(server.send("POST", "/api/projects/my-video/jobs", body))
        assert started.status == 202 and started.json()["job"]["mode"] == "restart"
        assert wait_final(server.runner).state == "done"
        synth = stub.calls()[-1]["argv"]
        assert synth == build_synth_argv(Path(synth[1]), project, voice="Leda", model=MODEL, language=None, instruction=None, scene=None)
        assert set(old).isdisjoint(snapshot(project)) and not list(project.rglob(".write-restart-*"))


GOOD = sidecar_bytes(sha(SCRIPT))


def test_beats_then_redo_beats_over_http_swap_the_candidate_in_and_the_detail_reads_it_as_fresh(stub_cli, tmp_path, loopback_only):
    stub = stub_cli(stdout=plan_stdout(BODIES), write_out_hex=GOOD.hex())
    with running_start_server(stub, tmp_path) as server:
        server.send("POST", "/api/projects", {"name": "My Video"})
        server.send("PUT", "/api/projects/my-video/script", {"text": SCRIPT.decode("utf-8")})
        project = tmp_path / "ws" / "my-video"
        for redo in (False, True):
            started = parse_response(server.send("POST", "/api/projects/my-video/jobs", beats_body(redo=redo)))
            assert started.status == 202 and started.json()["job"]["kind"] == ("beats-redo" if redo else "beats")
            assert wait_final(server.runner).state == "done"
            argv = stub.calls()[-1]["argv"]
            assert argv == build_beats_argv(Path(argv[1]), Path(argv[3]), BEATS_MODEL)
            assert (project / "beats.json").read_bytes() == GOOD
            detail = json.loads(parse_response(server.send("GET", "/api/projects/my-video")).body)
            assert detail["beats"]["state"] == "fresh" and sorted(p.name for p in project.iterdir()) == ["beats.json", "script.md"]
