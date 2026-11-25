import json
import signal
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from keys_server_helper import Running
from keys_web_helper import STATUS_STDOUT
from web_http_helper import parse_response
from web_run_helper import occupy_port

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.web import JobRunner, ignored_environment


def test_prints_the_message_and_opens_the_exact_link_after_binding(recorder):
    assert recorder.run() == 0
    link = recorder.link()
    assert recorder.opened == [link]
    assert link.startswith("http://127.0.0.1:") and "/?token=" in link
    assert recorder.opener_saw == {"printed_first": True}  # the opener also connected: already bound
    assert len(recorder.served) == 1


def test_no_open_skips_the_opener_but_still_prints_the_link(recorder):
    assert recorder.run(no_open=True) == 0
    assert recorder.opened == []
    assert "Open it here: http://127.0.0.1:" in recorder.out


@pytest.mark.parametrize("failure", ["raises", "false"])
def test_a_failing_opener_does_not_fail_the_command(recorder, failure):
    def opener(link):
        recorder.opened.append(link)
        if failure == "raises":
            raise RuntimeError("no browser")
        return False

    assert recorder.run(opener=opener) == 0
    assert recorder.opened and len(recorder.served) == 1


def test_a_busy_port_refuses_with_nothing_printed_opened_or_left_behind(recorder):
    held = occupy_port()
    try:
        port = held.getsockname()[1]
        assert recorder.run(port=port) == 1
    finally:
        held.close()
    err = recorder.err
    assert str(port) in err and "--port" in err
    assert "Open it here" not in recorder.out and "token" not in err
    assert recorder.opened == [] and recorder.served == []
    assert list(recorder.launch_root.iterdir()) == []


def test_control_c_closes_the_server_removes_the_launch_dir_and_exits_zero(recorder):
    def interrupted(server):
        recorder.served.append(server)
        raise KeyboardInterrupt

    assert recorder.run(serve=interrupted) == 0
    assert recorder.served[0].socket.fileno() == -1
    assert list(recorder.launch_root.iterdir()) == []
    assert recorder.out.rstrip().splitlines()[-1] == "SceneVoice has stopped."


def test_the_launch_dir_exists_while_serving_and_is_removed_on_any_exit(recorder):
    def failing(server):
        recorder.serve_saw["during"] = len(list(recorder.launch_root.iterdir()))
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        recorder.run(serve=failing)
    assert recorder.serve_saw["during"] == 1
    assert list(recorder.launch_root.iterdir()) == []


def probe(recorder, paths):
    """A serve callable that serves for real in a thread and asks `paths` with the cookie from the printed link."""
    results = []

    def serve(server):
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        recorder.serve_saw["launch_dirs"] = sorted(path.name for path in recorder.launch_root.iterdir())
        try:
            recorder.out += recorder.capsys.readouterr().out
            running = Running(server.port, recorder.link().split("token=")[1])
            results.extend(parse_response(running.send(method, path, body)) for method, path, body in paths)
        finally:
            server.shutdown()
            thread.join(5)

    return serve, results


def test_keys_routes_run_in_the_launch_dir_with_key_variables_removed_and_listed_as_ignored(recorder, stub_cli):
    stub = stub_cli(stdout=STATUS_STDOUT)
    environ = {name: "server-value" for name in KEY_NAMES} | {"HOME": "/h"}
    serve, results = probe(recorder, [("GET", "/api/keys", None)])
    assert recorder.run(serve=serve, environ=environ, prefix=stub.prefix, no_open=True) == 0
    assert results[0].status == 200
    assert results[0].json()["ignored_environment"] == ignored_environment(environ)
    recorded = stub.recording()
    assert recorded["cwd"] == str(Path(recorder.launch_root).resolve() / recorder.serve_saw["launch_dirs"][0])
    assert all(recorded["env"][name] is None for name in KEY_NAMES)
    assert "server-value" not in recorded["env_values"]


def test_a_relative_key_file_resolves_against_the_server_cwd_not_the_launch_dir(recorder, tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    environ = {"SCENEVOICE_KEYS_FILE": "rel/keys.env", "HOME": str(tmp_path / "home")}
    serve, results = probe(
        recorder, [("GET", "/api/keys", None), ("PUT", "/api/keys/OPENROUTER_API_KEY", {"value": "sk-test-1"})]
    )
    assert recorder.run(serve=serve, environ=environ, no_open=True) == 0
    assert [r.status for r in results] == [200, 200]
    assert json.loads(results[0].body)["path"] == str(work / "rel" / "keys.env")
    assert (work / "rel" / "keys.env").exists()
    assert list(recorder.launch_root.iterdir()) == []


def reveal_after_creating(recorder, tmp_path, **options):
    serve, results = probe(
        recorder, [("POST", "/api/projects", {"name": "My Video"}), ("POST", "/api/projects/my-video/reveal", {})]
    )
    code = recorder.run(serve=serve, workspace=tmp_path / "ws", environ={"HOME": "/h"}, no_open=True, **options)
    assert code == 0
    return results


def test_the_injected_launcher_receives_the_reveal_and_the_real_opener_is_never_started(recorder, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    started = []
    monkeypatch.setattr(
        sys.modules["scenevoice.web.run_opener"].subprocess, "run", lambda *a, **k: started.append(a)  # tripwire
    )
    launched = []
    results = reveal_after_creating(recorder, tmp_path, launch=lambda argv: launched.append(list(argv)) or 0)
    assert [r.status for r in results] == [201, 200]
    assert launched == [["open", str((tmp_path / "ws" / "my-video").resolve())]]
    assert started == []


def test_without_a_launch_argument_run_web_uses_the_real_opener_here_with_subprocess_patched(recorder, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    seen = []

    def fake_run(*args, **kwargs):
        seen.append(args[0])
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(sys.modules["scenevoice.web.run_opener"].subprocess, "run", fake_run)
    results = reveal_after_creating(recorder, tmp_path)
    assert [r.status for r in results] == [201, 200]
    assert seen == [["xdg-open", str((tmp_path / "ws" / "my-video").resolve())]]


STOP_SIGNALS = [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]


@pytest.fixture
def runners(monkeypatch):
    """Every JobRunner `run_web` builds, with the order of its shutdown against the server and launch dir recorded."""
    module = sys.modules["scenevoice.web.run_web"]
    built: list[dict] = []

    def factory(**options):
        runner = JobRunner(**options)
        entry = {"options": options, "runner": runner, "events": []}
        real_shutdown = runner.shutdown

        def shutdown():
            entry["events"].append(("shutdown", options["cwd"].exists(), entry["server"].socket.fileno() != -1))
            real_shutdown()

        runner.shutdown = shutdown
        built.append(entry)
        return runner

    monkeypatch.setattr(module, "JobRunner", factory)
    real_remove = module.remove_launch_dir
    monkeypatch.setattr(module, "remove_launch_dir", lambda path: (built[0]["events"].append(("remove",)), real_remove(path)))
    return built


def test_run_web_builds_one_runner_over_the_launch_dir_with_the_clean_child_environment(recorder, runners):
    environ = {name: "secret" for name in KEY_NAMES} | {"HOME": "/h"}

    def serve(server):
        runners[0]["server"] = server

    assert recorder.run(environ=environ, serve=serve, prefix=["stub"]) == 0
    assert len(runners) == 1
    options = runners[0]["options"]
    assert options["cwd"].name.startswith("scenevoice-web-")
    assert options["prefix"] == ["stub"]
    assert options["env"]["HOME"] == "/h" and not set(KEY_NAMES) & set(options["env"])


def test_the_runner_shuts_down_first_while_the_server_and_launch_dir_still_exist(recorder, runners):
    def serve(server):
        runners[0]["server"] = server
        raise KeyboardInterrupt

    assert recorder.run(serve=serve) == 0
    assert runners[0]["events"] == [("shutdown", True, True), ("remove",)]


def test_the_runner_also_shuts_down_when_serving_fails(recorder, runners):
    def serve(server):
        runners[0]["server"] = server
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        recorder.run(serve=serve)
    assert [event[0] for event in runners[0]["events"]] == ["shutdown", "remove"]


@pytest.mark.parametrize("sig", STOP_SIGNALS)
def test_each_stop_signal_ends_the_server_cleanly_and_the_old_handlers_come_back(recorder, runners, sig):
    before = {each: signal.getsignal(each) for each in STOP_SIGNALS}
    during: dict = {}

    def serve(server):
        runners[0]["server"] = server
        during.update({each: signal.getsignal(each) for each in STOP_SIGNALS})
        signal.raise_signal(sig)

    assert recorder.run(serve=serve) == 0
    assert all(during[each] != before[each] for each in STOP_SIGNALS)  # positive control: ours were installed
    assert {each: signal.getsignal(each) for each in STOP_SIGNALS} == before
    assert recorder.out.rstrip().splitlines()[-1] == "SceneVoice has stopped."
    assert list(recorder.launch_root.iterdir()) == []


@pytest.mark.parametrize("second", STOP_SIGNALS)
def test_a_second_signal_after_the_first_is_ignored_until_the_handlers_are_restored(recorder, runners, second):
    outcome: list[str] = []

    def serve(server):
        runners[0]["server"] = server
        try:
            signal.raise_signal(signal.SIGINT)
        except KeyboardInterrupt:
            outcome.append("first")
            signal.raise_signal(second)  # latched: no second KeyboardInterrupt
            outcome.append("second ignored")
            raise

    assert recorder.run(serve=serve) == 0
    assert outcome == ["first", "second ignored"]


def test_the_project_routes_get_the_runners_job_active_so_the_detail_hides_kept_backups_while_a_job_runs(recorder, runners, monkeypatch):
    module = sys.modules["scenevoice.web.run_web"]
    seen = []
    real = module.ProjectRoutes
    monkeypatch.setattr(module, "ProjectRoutes", lambda **options: seen.append(options) or real(**options))

    def serve(server):
        runners[0]["server"] = server

    assert recorder.run(serve=serve) == 0
    assert len(seen) == 1  # positive control: the spy saw the one construction
    assert seen[0]["job_active"] == runners[0]["runner"].job_active


def test_p1_catalog_route_is_merged_by_run_web_and_equals_the_registry_voices_and_default_language(recorder):
    from scenevoice.synth import DEFAULT_LANGUAGE, PROVIDERS, VOICES

    serve, results = probe(recorder, [("GET", "/api/catalog", None)])
    assert recorder.run(serve=serve, no_open=True) == 0
    assert results[0].status == 200
    by_id = dict(zip(("vertex", "elevenlabs"), PROVIDERS, strict=True))
    assert results[0].json() == {
        "providers": {
            name: {"models": list(spec.models), "env_names": list(spec.env_names), "voices": None if spec.voices is None else list(VOICES)}
            for name, spec in by_id.items()
        },
        "default_language": DEFAULT_LANGUAGE,
    }
    assert results[0].json()["providers"]["elevenlabs"]["voices"] is None
