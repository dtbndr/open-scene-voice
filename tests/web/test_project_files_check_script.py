import base64
import json
import os
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from project_routes_helper import make_project_routes
from web_http_helper import make_request

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.web import (
    absolute_keys_file,
    bind_runner,
    check_script,
    child_env,
    post_reveal,
)

PLAN = json.dumps({"scenes": [{"title": "a b"}, {"title": "c\u0085d"}]}, ensure_ascii=False, indent=2) + "\n"
OK_EVENT = json.dumps({"command": "plan", "event": "ok", "message": "OK {path}"})
SAVED = "saved script\r\n"


def fail_event(message="{path}: Scene 2 is empty (line 7)", line=7, kind="invalid_input"):
    return json.dumps(
        {"command": "plan", "event": "fail", "message": message, "kind": kind, "scene": None, "line": line, "status": None}
    )


@pytest.fixture
def launch(tmp_path):
    directory = tmp_path.resolve() / "launch"
    directory.mkdir(mode=0o700)
    return directory


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path.resolve() / "ws"
    (root / "p").mkdir(parents=True)
    (root / "p" / "script.md").write_bytes(SAVED.encode())
    return root


@pytest.fixture
def check(stub_cli, launch, workspace):
    """`check(text, stub=..., timeout=..., project_id=...) -> (response, body, stub)` over the stub as the CLI."""

    def make(handler_stub, timeout=10.0, lock=None):
        environ = {**{name: "secret-value" for name in KEY_NAMES}, "HOME": "/h"}
        run = bind_runner(launch, child_env(absolute_keys_file(environ)), handler_stub.prefix)
        return check_script(lambda: workspace, "p", run, launch, lock or threading.Lock(), timeout)

    def call(handler, body):
        response = handler(replace(make_request("POST", "/api/projects/p/check"), json_body=body))
        return response, json.loads(response.body)

    make.call = call
    return make


def spec(stub_cli, **options):
    return stub_cli(record_files=[-1], **options)


def recorded_path(stub):
    return stub.recording()["files"][0]["path"]


def assert_path_absent(response, path):
    assert path not in response.body.decode() and path not in repr(response.headers)


def test_an_accepted_script_answers_ok_with_the_scene_count(check, stub_cli):
    stub = spec(stub_cli, stdout=PLAN, stderr_lines=[OK_EVENT])
    response, body = check.call(check(stub), {"text": "x"})
    assert (response.status, response.no_store, body) == (200, True, {"ok": True, "scenes": 2})
    assert len(stub.calls()) == 1  # positive control: the answer came from the stub


def test_a_violation_is_an_expected_200_with_one_problem(check, stub_cli):
    stub = spec(stub_cli, exit_code=1, stderr_lines=[fail_event()])
    response, body = check.call(check(stub), {"text": "x"})
    assert (response.status, body) == (200, {"ok": False, "problems": [{"line": 7, "message": "Scene 2 is empty"}]})
    assert_path_absent(response, recorded_path(stub))


def test_the_child_gets_the_plan_command_with_the_absolute_temp_path_in_the_launch_directory(check, stub_cli, launch):
    stub = spec(stub_cli, stdout=PLAN, stderr_lines=[OK_EVENT], record_env=["HOME", *KEY_NAMES])
    check.call(check(stub), {"text": "x"})
    call = stub.calls()[0]
    path = Path(call["files"][0]["path"])
    assert call["argv"] == ["plan", "--progress", "json", str(path)]
    assert path.is_absolute() and path.parent == launch
    assert call["cwd"] == str(launch)
    assert call["env"]["HOME"] == "/h"
    assert [call["env"][name] for name in KEY_NAMES] == [None] * len(KEY_NAMES)


def test_the_child_reads_the_unsaved_text_exactly_from_a_private_file_outside_the_workspace(check, stub_cli, workspace, launch):
    text = "﻿One\r\nTwo x\u0085y é ✓ 😀"
    stub = spec(stub_cli, stdout=PLAN, stderr_lines=[OK_EVENT])
    check.call(check(stub), {"text": text})
    entry = stub.recording()["files"][0]
    assert base64.b64decode(entry["bytes_b64"]) == text.encode("utf-8")
    assert entry["mode"] == 0o600
    assert Path(entry["path"]).parent == launch and workspace not in Path(entry["path"]).parents
    assert (workspace / "p" / "script.md").read_bytes() == SAVED.encode()  # the saved script is not touched
    assert sorted(os.listdir(workspace / "p")) == ["script.md"]


@pytest.mark.parametrize("case", ["ok", "violation", "timeout", "bad_output", "other_fail"])
def test_nothing_stays_on_disk_and_the_temp_path_is_never_echoed(check, stub_cli, launch, case):
    options = {
        "ok": {"stdout": PLAN, "stderr_lines": [OK_EVENT]},
        "violation": {"exit_code": 1, "stderr_lines": [fail_event()]},
        "timeout": {"sleep": 3, "stdout": PLAN},
        "bad_output": {"stdout": "not json", "stderr_lines": ["leak {path}"]},
        "other_fail": {"exit_code": 1, "stderr_lines": [fail_event(kind="other")]},
    }[case]
    stub = spec(stub_cli, **options)
    response, body = check.call(check(stub, timeout=0.4 if case == "timeout" else 10.0), {"text": "x"})
    assert os.listdir(launch) == []
    assert_path_absent(response, recorded_path(stub))
    if case in ("bad_output", "other_fail", "timeout"):
        assert (response.status, body["error"]["kind"]) == (502, "cli_failed")
        assert body["error"]["message"]


def test_an_unreadable_temp_file_report_is_a_502_not_a_script_problem(check, stub_cli):
    stub = spec(stub_cli, exit_code=1, stderr_lines=[fail_event("{path}: cannot read file (nope)", line=None)])
    response, body = check.call(check(stub), {"text": "x"})
    assert (response.status, body["error"]["kind"]) == (502, "cli_failed")


def test_a_non_zero_exit_without_a_usable_event_is_a_502(check, stub_cli):
    stub = spec(stub_cli, exit_code=1, stderr_lines=["noise"])
    assert check.call(check(stub), {"text": "x"})[0].status == 502


@pytest.mark.parametrize("body", [None, [], "text", {"text": 3}, {"txt": "x"}, {"text": "\ud800"}])
def test_a_body_without_text_is_a_400_and_never_reaches_the_cli(check, stub_cli, launch, body):
    stub = spec(stub_cli, stdout=PLAN)
    response, answer = check.call(check(stub), body)
    assert (response.status, answer["error"]["kind"]) == (400, "bad_request")
    assert stub.calls() == [] and os.listdir(launch) == []


def test_a_missing_project_is_a_404_with_no_child_while_an_existing_one_calls_the_stub(check, stub_cli, workspace):
    stub = spec(stub_cli, stdout=PLAN, stderr_lines=[OK_EVENT])
    handler = check(stub)
    (workspace / "p" / "script.md").unlink()
    (workspace / "p").rmdir()
    response, body = check.call(handler, {"text": "x"})
    assert (response.status, body["error"]["kind"]) == (404, "not_found")
    assert stub.calls() == []
    (workspace / "p").mkdir()  # no script.md needed
    assert check.call(handler, {"text": "x"})[0].status == 200
    assert len(stub.calls()) == 1


def wait_until(condition, limit=10.0):
    deadline = time.monotonic() + limit
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return condition()


def test_two_overlapping_checks_never_run_together_and_the_lock_is_released_after_a_timeout(check, stub_cli, tmp_path):
    release = tmp_path / "release"
    stub = spec(stub_cli, stdout=PLAN, stderr_lines=[OK_EVENT], wait_for_file=str(release))
    handler = check(stub, timeout=0.6)
    answers = []
    first = threading.Thread(target=lambda: answers.append(check.call(handler, {"text": "1"})))
    first.start()
    assert wait_until(lambda: [e["event"] for e in stub.events()] == ["start"])
    second = threading.Thread(target=lambda: answers.append(check.call(handler, {"text": "2"})))
    second.start()
    time.sleep(0.2)
    assert [e["event"] for e in stub.events()] == ["start"]  # the second waits for the lock
    first.join(10)  # the first times out (0.6 s) without the release file
    release.write_text("go")
    second.join(10)
    assert sorted(a[0].status for a in answers) == [200, 502]
    assert [e["event"] for e in stub.events()] == ["start", "start", "end"]  # killed child never ends; the lock freed


def test_the_lock_is_shared_by_every_request_of_one_server_through_the_route_table(stub_cli, launch, workspace, tmp_path):
    release = tmp_path / "release"
    stub = spec(stub_cli, stdout=PLAN, stderr_lines=[OK_EVENT], wait_for_file=str(release))
    routes = make_project_routes(root_getter=lambda: workspace, run=bind_runner(launch, {"HOME": "/h"}, stub.prefix), launch_dir=launch)
    request = replace(make_request("POST", "/api/projects/p/check"), json_body={"text": "x"})
    threads = [threading.Thread(target=lambda: routes["/api/projects/p/check"]["POST"](request)) for _ in range(2)]
    threads[0].start()
    assert wait_until(lambda: len(stub.events()) == 1)
    threads[1].start()
    time.sleep(0.2)
    assert [e["event"] for e in stub.events()] == ["start"]
    release.write_text("go")
    for thread in threads:
        thread.join(10)
    assert [e["event"] for e in stub.events()] == ["start", "end", "start", "end"]


@pytest.fixture
def project(tmp_path):
    directory = tmp_path.resolve() / "ws" / "my-video"
    directory.mkdir(parents=True)
    return directory


class Recorder:
    def __init__(self, result=0, raises=None):
        self.result, self.raises, self.calls = result, raises, []

    def __call__(self, argv):
        self.calls.append(list(argv))
        if self.raises:
            raise self.raises
        return self.result


def ask(project, launch, project_id="my-video", platform="darwin", body=None):
    handler = post_reveal(lambda: project.parent, project_id, launch, platform)
    return handler(replace(make_request("POST", f"/api/projects/{project_id}/reveal"), json_body={} if body is None else body))


def kind(response):
    error = json.loads(response.body)["error"]
    return (response.status, error["kind"], error["message"])


@pytest.mark.parametrize(("platform", "program"), [("darwin", "open"), ("linux", "xdg-open")])
def test_success_is_a_200_ok_and_the_launcher_got_the_validated_absolute_directory(project, platform, program):
    launch = Recorder()
    response = ask(project, launch, platform=platform)
    assert (response.status, json.loads(response.body)) == (200, {"ok": True})
    assert response.no_store is True
    assert launch.calls == [[program, str(project)]]


def test_a_non_zero_exit_an_oserror_and_a_timeout_result_are_a_502_with_no_path_in_the_message(project):
    for launch in (Recorder(result=1), Recorder(result=-1), Recorder(raises=FileNotFoundError(str(project)))):
        status, error_kind, message = kind(ask(project, launch))
        assert (status, error_kind) == (502, "cli_failed")
        assert str(project) not in message and "my-video" not in message
        assert len(launch.calls) == 1  # positive control: the failure came from a launcher that was called


def test_an_unsupported_platform_is_a_501_with_a_plain_sentence_and_the_launcher_is_not_called(project):
    launch = Recorder()
    status, error_kind, message = kind(ask(project, launch, platform="win32"))
    assert (status, error_kind) == (501, "unsupported")
    assert message.endswith(".") and str(project) not in message
    assert launch.calls == []


@pytest.mark.parametrize("project_id", ["other", "My Video", "../x"])
def test_a_missing_project_or_invalid_id_is_a_404_and_nothing_is_launched(project, project_id):
    launch = Recorder()
    assert kind(ask(project, launch, project_id))[:2] == (404, "not_found")
    assert launch.calls == []


@pytest.mark.parametrize("body", [{}, {"anything": 1}, [1, 2], "text", None])
def test_the_body_content_is_ignored(project, body):
    launch = Recorder()
    handler = post_reveal(lambda: project.parent, "my-video", launch, "darwin")
    assert handler(replace(make_request("POST", "/api/projects/my-video/reveal"), json_body=body)).status == 200
    assert launch.calls == [["open", str(project)]]


def test_a_symlinked_project_is_a_404_and_nothing_is_launched(project):
    (project.parent / "linked").symlink_to(project)
    launch = Recorder()
    assert kind(ask(project, launch, "linked"))[:2] == (404, "not_found")
    assert launch.calls == []
