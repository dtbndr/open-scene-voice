import json
import threading
import time
from dataclasses import replace

import pytest
from keys_web_helper import (
    NAME,
    STATUS,
    STATUS_STDOUT,
    call,
    routes_over,
)
from web_http_helper import make_request

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.web import ignored_environment

OTHER = "ELEVENLABS_API_KEY"
SETTLE = 0.2


def blocking_stub(stub_cli, release, **spec):
    return stub_cli(stdout=STATUS_STDOUT, by_verb={"set": {"wait_for_file": str(release)}, "remove": {"wait_for_file": str(release)}}, **spec)


def mutation_events(stub):
    return [(e["event"], e["argv"][1]) for e in stub.events() if e["argv"][1] in ("set", "remove")]


def wait_until(condition, limit=10.0):
    deadline = time.monotonic() + limit
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return condition()


def run_in_thread(routes, method, path, body=None):
    results = []
    thread = threading.Thread(target=lambda: results.append(call(routes, method, path, body)))
    thread.start()
    return thread, results


def settle(stub, starts):
    """Wait for `starts` mutation starts, then give a wrongly unlocked second call time to show up."""
    assert wait_until(lambda: sum(1 for e in mutation_events(stub) if e[0] == "start") >= starts)
    time.sleep(SETTLE)


def test_two_puts_for_different_names_never_overlap(stub_cli, tmp_path):
    release = tmp_path / "release"
    stub = blocking_stub(stub_cli, release)
    routes = routes_over(stub, tmp_path)
    first, _ = run_in_thread(routes, "PUT", f"/api/keys/{NAME}", {"value": "a"})
    assert wait_until(lambda: mutation_events(stub) == [("start", "set")])
    second, _ = run_in_thread(routes, "PUT", f"/api/keys/{OTHER}", {"value": "b"})
    settle(stub, 1)
    assert mutation_events(stub) == [("start", "set")]
    release.write_text("go")
    first.join(10)
    second.join(10)
    assert mutation_events(stub) == [("start", "set"), ("end", "set"), ("start", "set"), ("end", "set")]


def test_a_put_and_a_delete_never_overlap(stub_cli, tmp_path):
    release = tmp_path / "release"
    stub = blocking_stub(stub_cli, release)
    routes = routes_over(stub, tmp_path)
    first, _ = run_in_thread(routes, "PUT", f"/api/keys/{NAME}", {"value": "a"})
    assert wait_until(lambda: mutation_events(stub) == [("start", "set")])
    second, _ = run_in_thread(routes, "DELETE", f"/api/keys/{OTHER}")
    settle(stub, 1)
    assert mutation_events(stub) == [("start", "set")]
    release.write_text("go")
    first.join(10)
    second.join(10)
    assert mutation_events(stub) == [("start", "set"), ("end", "set"), ("start", "remove"), ("end", "remove")]


def test_get_is_not_blocked_by_a_running_mutation(stub_cli, tmp_path):
    release = tmp_path / "release"
    stub = blocking_stub(stub_cli, release)
    routes = routes_over(stub, tmp_path)
    writer, _ = run_in_thread(routes, "PUT", f"/api/keys/{NAME}", {"value": "a"})
    assert wait_until(lambda: mutation_events(stub) == [("start", "set")])
    reader, results = run_in_thread(routes, "GET", "/api/keys")
    reader.join(10)
    assert not reader.is_alive()
    assert results[0].status == 200
    assert mutation_events(stub) == [("start", "set")]
    release.write_text("go")
    writer.join(10)


def test_the_lock_is_released_after_a_timeout_and_after_a_failure(stub_cli, tmp_path):
    stub = stub_cli(sleep=5, stdout=STATUS_STDOUT)
    routes = routes_over(stub, tmp_path, timeout=0.3)
    assert call(routes, "PUT", f"/api/keys/{NAME}", {"value": "a"}).status == 502
    stub = stub_cli(exit_code=1)
    assert call(routes, "PUT", f"/api/keys/{NAME}", {"value": "a"}).status == 502
    stub = stub_cli(stdout=STATUS_STDOUT)
    done = []
    worker = threading.Thread(target=lambda: done.append(call(routes, "DELETE", f"/api/keys/{NAME}")))
    worker.start()
    worker.join(10)
    assert not worker.is_alive()
    assert done[0].status == 200
    assert json.loads(done[0].body)["path"]
    assert [c["argv"][1] for c in stub.calls()][-2:] == ["remove", "status"]


def test_two_servers_do_not_share_a_lock(stub_cli, tmp_path):
    release = tmp_path / "release"
    stub = blocking_stub(stub_cli, release)
    one = routes_over(stub, tmp_path)
    two = routes_over(stub, tmp_path)
    first, _ = run_in_thread(one, "PUT", f"/api/keys/{NAME}", {"value": "a"})
    second, _ = run_in_thread(two, "PUT", f"/api/keys/{OTHER}", {"value": "b"})
    assert wait_until(lambda: [e[0] for e in mutation_events(stub)] == ["start", "start"])
    release.write_text("go")
    first.join(10)
    second.join(10)


KEY_PATH = f"/api/keys/{NAME}"
GENERIC = "The key could not be saved."


def view(**changes):
    return {**STATUS, "suggested_region": "global", "ignored_environment": [], **changes}


def error(response):
    return response.status, json.loads(response.body)["error"]


def test_get_runs_keys_status_and_returns_the_view(stub_cli, tmp_path):
    stub = stub_cli(stdout=STATUS_STDOUT)
    routes = routes_over(stub, tmp_path, ignored_environment=["OPENROUTER_API_KEY"])
    response = call(routes, "GET", "/api/keys")
    assert response.status == 200
    assert response.no_store
    assert json.loads(response.body) == view(ignored_environment=["OPENROUTER_API_KEY"])
    assert [c["argv"] for c in stub.calls()] == [["keys", "status"]]
    assert stub.calls()[0]["stdin"] == b""


def test_put_sets_with_value_on_stdin_only_then_returns_fresh_status(stub_cli, tmp_path):
    stub = stub_cli(stdout=STATUS_STDOUT)
    response = call(routes_over(stub, tmp_path), "PUT", KEY_PATH, {"value": "s3cret-value"})
    assert response.status == 200
    assert json.loads(response.body) == view()
    calls = stub.calls()
    assert [c["argv"] for c in calls] == [["keys", "set", NAME], ["keys", "status"]]
    assert calls[0]["stdin"] == b"s3cret-value"
    assert calls[1]["stdin"] == b""
    assert "s3cret-value" not in json.dumps(calls[0]["argv"])


def test_delete_removes_then_returns_fresh_status(stub_cli, tmp_path):
    stub = stub_cli(stdout=STATUS_STDOUT)
    response = call(routes_over(stub, tmp_path), "DELETE", KEY_PATH)
    assert response.status == 200
    assert json.loads(response.body) == view()
    assert [c["argv"] for c in stub.calls()] == [["keys", "remove", NAME], ["keys", "status"]]


@pytest.mark.parametrize(("method", "name"), [("PUT", "NOPE"), ("DELETE", "../x")])  # outside the key list: no CLI run
def test_unknown_name_is_not_found_and_nothing_runs(stub_cli, tmp_path, method, name):
    stub = stub_cli(stdout=STATUS_STDOUT)
    routes = routes_over(stub, tmp_path)
    request = replace(make_request(method, f"/api/keys/{name}"), json_body={"value": "x"})
    response = routes[KEY_PATH][method](request)
    assert error(response)[0] == 404
    assert error(response)[1]["kind"] == "not_found"
    assert stub.calls() == []


@pytest.mark.parametrize("body", [[], {"value": 5}, {}])
def test_bad_put_body_is_bad_request_and_nothing_runs(stub_cli, tmp_path, body):
    stub = stub_cli(stdout=STATUS_STDOUT)
    response = call(routes_over(stub, tmp_path), "PUT", KEY_PATH, body)
    assert error(response)[0] == 400
    assert error(response)[1]["kind"] == "bad_request"
    assert stub.calls() == []


def test_cli_refusal_passes_the_one_line_fail_message_through(stub_cli, tmp_path):
    stub = stub_cli(
        exit_code=1,
        stderr_lines=["scenevoice keys: NOTE fixed a mode", "scenevoice keys: FAIL OPENROUTER_API_KEY: the value has a newline"],
    )
    response = call(routes_over(stub, tmp_path), "PUT", KEY_PATH, {"value": "QQQ"})
    assert error(response) == (400, {"kind": "bad_request", "message": "OPENROUTER_API_KEY: the value has a newline"})
    assert len(stub.calls()) == 1


# Key leak: a CLI message echoing the submitted value never reaches the response.
def test_echoed_value_in_the_fail_message_is_replaced_by_a_fixed_message(stub_cli, tmp_path):
    stub = stub_cli(exit_code=1, stderr_lines=["scenevoice keys: FAIL bad value s3cret-value here"])
    response = call(routes_over(stub, tmp_path), "PUT", KEY_PATH, {"value": "s3cret-value"})
    assert error(response) == (400, {"kind": "bad_request", "message": GENERIC})
    assert b"s3cret-value" not in response.body


@pytest.mark.parametrize(
    "spec",
    [
        {"exit_code": 1, "stderr_lines": ["unrelated traceback line"]},
        {"stdout": "not json"},
        {"stdout": json.dumps({"keys": STATUS["keys"]})},
    ],
)
def test_unusable_cli_result_is_cli_failed(stub_cli, tmp_path, spec):
    stub = stub_cli(**spec)
    status, body = error(call(routes_over(stub, tmp_path), "GET", "/api/keys"))
    assert (status, body["kind"]) == (502, "cli_failed")


def test_ignored_environment_names_only_non_blank_key_variables():
    environ = {name: "x" for name in KEY_NAMES}
    environ["OPENROUTER_API_KEY"] = "  "
    environ["GOOGLE_CLOUD_LOCATION"] = ""
    environ["HOME"] = "/h"
    assert ignored_environment(environ) == [
        "GOOGLE_CLOUD_PROJECT",
        "VERTEX_AUTHORIZATION_KEY",
        "ELEVENLABS_API_KEY",
    ]
    assert ignored_environment({"HOME": "/h"}) == []
