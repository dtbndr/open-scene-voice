import dataclasses
import io
import json
import os
import sys

import pytest

from scenevoice.synth import ENV_NAMES, PlanScene
from scenevoice.synth.preflight_result import PreflightResult
from scenevoice.synth.run_preflight import run_preflight

MODULE = "scenevoice.synth.run_preflight"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}


def plan_bytes(n=1, body="b"):
    scenes = [{"ordinal": i, "title": "t", "body": body} for i in range(1, n + 1)]
    return json.dumps({"scenes": scenes}).encode("utf-8")


class FakeStdin:
    def __init__(self, data=b"", tty=False):
        self.buffer = io.BytesIO(data)
        self.tty = tty
        self.reads = 0
        self.isatty_calls = 0
        outer = self
        real = self.buffer

        class Spy:
            def read(self_inner):
                outer.reads += 1
                return real.read()

        self.buffer = Spy()

    def isatty(self):
        self.isatty_calls += 1
        return self.tty


class NoBufferStdin:
    def isatty(self):
        return False


class BrokenStdin:
    class buffer:
        @staticmethod
        def read():
            raise OSError(5, "Input/output error")

    def isatty(self):
        return False


@pytest.fixture
def plan_file(tmp_path):
    path = tmp_path / "plan.json"
    path.write_bytes(plan_bytes(2))
    return path


@pytest.fixture
def spies(monkeypatch):
    """Record resolve_env and prepare_out_dir calls through the module object."""
    module = sys.modules[MODULE]
    calls = {"resolve_env": [], "prepare_out_dir": []}
    real_resolve, real_prepare = module.resolve_env, module.prepare_out_dir

    def resolve(*args, **kwargs):
        calls["resolve_env"].append(args)
        return real_resolve(*args, **kwargs)

    def prepare(*args, **kwargs):
        calls["prepare_out_dir"].append(args)
        return real_prepare(*args, **kwargs)

    monkeypatch.setattr(module, "resolve_env", resolve)
    monkeypatch.setattr(module, "prepare_out_dir", prepare)
    return calls


def run(tmp_path, plan_path, stdin=None, env=ENV, out=None):
    return run_preflight(
        plan_path,
        stdin,
        env,
        tmp_path / "absent.env",
        out if out is not None else tmp_path / "out",
    )


def assert_failure(result):
    assert isinstance(result, str)
    assert not result.startswith("scenevoice synth")
    assert "dummy-key-value" not in result


# step 1


def test_terminal_stdin_without_plan_fails_before_any_io(tmp_path, spies):
    stdin = FakeStdin(plan_bytes(), tty=True)
    out = tmp_path / "out"
    result = run(tmp_path, None, stdin, out=out)
    assert_failure(result)
    assert "terminal" in result
    assert stdin.reads == 0
    assert spies["resolve_env"] == []
    assert spies["prepare_out_dir"] == []
    assert not out.exists()


def test_terminal_stdin_with_plan_path_proceeds_and_never_reads_stdin(
    tmp_path, spies, plan_file
):
    stdin = FakeStdin(b"ignored", tty=True)
    result = run(tmp_path, plan_file, stdin)
    assert isinstance(result, PreflightResult)
    assert stdin.reads == 0
    assert len(spies["resolve_env"]) == 1  # positive control


def test_non_terminal_stdin_without_plan_is_read(tmp_path, spies):
    stdin = FakeStdin(plan_bytes(), tty=False)
    result = run(tmp_path, None, stdin)
    assert isinstance(result, PreflightResult)
    assert stdin.reads == 1
    assert len(spies["resolve_env"]) == 1


# step 2


def test_unreadable_path_reports_cannot_read_and_stops(tmp_path, spies):
    out = tmp_path / "out"
    result = run(tmp_path, tmp_path / "missing.json", out=out)
    assert_failure(result)
    assert "cannot read file (" in result
    assert spies["resolve_env"] == []
    assert not out.exists()


def test_directory_as_plan_reports_cannot_read(tmp_path, spies):
    result = run(tmp_path, tmp_path)
    assert_failure(result)
    assert "cannot read file (" in result
    assert spies["resolve_env"] == []


@pytest.mark.parametrize(
    "stdin", [FakeStdin(b""), BrokenStdin(), NoBufferStdin()], ids=["empty", "oserror", "nobuffer"]
)
def test_bad_stdin_reports_cannot_read(tmp_path, spies, stdin):
    result = run(tmp_path, None, stdin)
    assert_failure(result)
    assert "cannot read file (" in result
    assert spies["resolve_env"] == []
    assert not (tmp_path / "out").exists()


# step 3


def test_invalid_plan_fails_and_leaves_new_dir_uncreated(tmp_path, spies):
    plan = tmp_path / "plan.json"
    plan.write_bytes(b"not json")
    out = tmp_path / "new" / "out"
    result = run(tmp_path, plan, out=out)
    assert_failure(result)
    assert spies["resolve_env"] == []
    assert spies["prepare_out_dir"] == []
    assert not out.exists()
    assert not out.parent.exists()


def test_1000_scenes_fails_on_count_even_when_over_byte_limit(tmp_path, spies):
    plan = tmp_path / "plan.json"
    plan.write_bytes(plan_bytes(1000, body="x" * 9000))
    result = run(tmp_path, plan)
    assert_failure(result)
    assert "1000 scenes" in result
    assert "bytes" not in result
    assert spies["resolve_env"] == []


def test_over_limit_scenes_name_every_ordinal_and_byte_count(tmp_path, spies):
    plan = tmp_path / "plan.json"
    plan.write_bytes(plan_bytes(2, body="x" * 9000))
    result = run(tmp_path, plan)
    assert_failure(result)
    assert "scene 1: 9000 bytes" in result
    assert "scene 2: 9000 bytes" in result
    assert spies["resolve_env"] == []


# step 4


def test_missing_env_names_listed_in_fixed_order_without_values(
    tmp_path, spies, plan_file
):
    out = tmp_path / "out"
    env = {"GOOGLE_CLOUD_LOCATION": "secret-location-value"}
    result = run(tmp_path, plan_file, env=env, out=out)
    assert_failure(result)
    names = [n for n in ENV_NAMES if n != "GOOGLE_CLOUD_LOCATION"]
    positions = [result.index(n) for n in names]
    assert positions == sorted(positions)
    assert "GOOGLE_CLOUD_LOCATION" not in result
    assert "secret-location-value" not in result
    assert len(spies["resolve_env"]) == 1
    assert spies["prepare_out_dir"] == []
    assert not out.exists()


def test_unreadable_dotenv_fails_naming_dotenv(tmp_path, spies, plan_file):
    dotenv = tmp_path / "bad.env"
    dotenv.write_bytes(b"GOOGLE_CLOUD_PROJECT=\xff\xfe\n")
    out = tmp_path / "out"
    result = run_preflight(plan_file, None, {}, dotenv, out)
    assert_failure(result)
    assert ".env" in result
    assert spies["prepare_out_dir"] == []
    assert not out.exists()


# step 5


@pytest.mark.parametrize("dangling", [False, True], ids=["file", "dangling-symlink"])
def test_collision_fails_and_creates_no_dir(tmp_path, spies, plan_file, dangling):
    out = tmp_path / "existing"
    (out / "audio").mkdir(parents=True)
    if dangling:
        (out / "audio" / "002.wav").symlink_to(tmp_path / "nowhere")
    else:
        (out / "audio" / "002.wav").write_bytes(b"old")
    result = run(tmp_path, plan_file, out=out)
    assert_failure(result)
    assert "audio/002.wav" in result
    assert spies["prepare_out_dir"] == []
    assert sorted(os.listdir(out)) == ["audio"]
    assert sorted(os.listdir(out / "audio")) == ["002.wav"]


def test_collision_check_works_when_dir_does_not_exist(tmp_path, spies, plan_file):
    out = tmp_path / "fresh"
    result = run(tmp_path, plan_file, out=out)
    assert isinstance(result, PreflightResult)
    assert len(spies["prepare_out_dir"]) == 1  # positive control
    assert out.is_dir()


def test_regular_file_as_out_fails_at_step_5(tmp_path, spies, plan_file):
    out = tmp_path / "afile"
    out.write_bytes(b"x")
    result = run(tmp_path, plan_file, out=out)
    assert_failure(result)
    assert spies["prepare_out_dir"] == []
    assert out.read_bytes() == b"x"


# step 6 and 7


def test_dangling_symlink_out_passes_step_5_and_fails_at_step_6(
    tmp_path, spies, plan_file
):
    out = tmp_path / "link"
    out.symlink_to(tmp_path / "missing")
    result = run(tmp_path, plan_file, out=out)
    assert_failure(result)
    assert len(spies["prepare_out_dir"]) == 1
    assert not (tmp_path / "missing").exists()


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="permissions not enforced for root"
)
def test_unwritable_dir_fails_the_probe(tmp_path, spies, plan_file):
    out = tmp_path / "ro"
    out.mkdir()
    out.chmod(0o500)
    try:
        result = run(tmp_path, plan_file, out=out)
    finally:
        out.chmod(0o700)
    assert_failure(result)
    assert len(spies["prepare_out_dir"]) == 1
    assert os.listdir(out) == []


# success


def test_existing_dir_accepted_with_stale_file_untouched(tmp_path, plan_file):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / "audio" / "007.wav").write_bytes(b"stale")
    result = run(tmp_path, plan_file, out=out)
    assert isinstance(result, PreflightResult)
    assert (out / "audio" / "007.wav").read_bytes() == b"stale"
    assert sorted(os.listdir(out)) == ["audio"]
    assert sorted(os.listdir(out / "audio")) == ["007.wav"]


def test_success_returns_scenes_and_resolved_env(tmp_path, plan_file):
    out = tmp_path / "out"
    result = run(tmp_path, plan_file, out=out)
    assert isinstance(result, PreflightResult)
    assert result.scenes == [PlanScene(1, "t", "b"), PlanScene(2, "t", "b")]
    assert result.env == ENV
    assert os.listdir(out) == ["audio"] and os.listdir(out / "audio") == []


def test_dotenv_values_are_resolved_when_process_env_is_empty(tmp_path, plan_file):
    dotenv = tmp_path / "real.env"
    dotenv.write_text("".join(f"{k}={v}\n" for k, v in ENV.items()))
    result = run_preflight(plan_file, None, {}, dotenv, tmp_path / "out")
    assert isinstance(result, PreflightResult)
    assert result.env == ENV


def test_preflight_result_is_frozen():
    result = PreflightResult([], {})
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.env = {}
