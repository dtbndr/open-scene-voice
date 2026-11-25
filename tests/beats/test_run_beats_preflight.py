"""Checks that fail before the key is looked up or the model is called."""

import io

import pytest
from beats_run_helper import (
    GOOD,
    PREFIX,
    SCRIPT,
    replying,
    run,
)
from chat_run_helper import KEY

from scenevoice.beats import run_beats
from scenevoice.validation import load_scenes

pytestmark = pytest.mark.usefixtures("no_sockets")


@pytest.mark.parametrize(
    "script",
    [b"\xff\xfe bad", b"\xef\xbb\xbf## One\nHi there.\n", b"no heading here\n", b"## One\n\n"],
    ids=["undecodable", "bom", "no-scene", "empty-scene"],
)
def test_bad_scripts_fail_before_key_and_call(tmp_path, script):
    fake = replying(GOOD)
    code, err, out = run(tmp_path, fake, script=script, env={})
    assert code == 1
    assert fake.keys == [] and fake.requests == []
    assert not out.exists()
    lines = err.splitlines()
    assert len(lines) == 1 and lines[0].startswith(PREFIX + "FAIL SCRIPT: ")
    assert "OPENROUTER_API_KEY" not in err


def test_plan_check_failure_message_has_exact_shape(tmp_path):
    scenes = load_scenes(b"no heading here\n")
    code, err, _ = run(tmp_path, replying(GOOD), script=b"no heading here\n")
    suffix = f" (line {scenes.line})" if scenes.line is not None else ""
    assert err.splitlines() == [
        f"{PREFIX}FAIL SCRIPT: it does not pass the plan check: {scenes.message}{suffix}"
    ]


def test_missing_script_names_the_path(tmp_path):
    fake = replying(GOOD)
    missing = tmp_path / "missing.md"
    code, err, _ = run(tmp_path, fake, script=None, script_path=missing)
    assert code == 1
    assert fake.keys == []
    assert err.splitlines() == [
        f"{PREFIX}FAIL SCRIPT: could not read the script {missing} (No such file or directory)"
    ]


def test_over_the_cap_script_fails_before_key_and_call(tmp_path):
    from scenevoice.beats import MAX_SCRIPT_CHARS, SCRIPT_TOO_LONG_MESSAGE

    big = b"## One\n" + b"a" * MAX_SCRIPT_CHARS + b"\n"
    fake = replying(GOOD)
    code, err, _ = run(tmp_path, fake, script=big, env={})
    assert code == 1
    assert fake.keys == [] and fake.requests == []
    assert err.splitlines() == [f"{PREFIX}FAIL SCRIPT: {SCRIPT_TOO_LONG_MESSAGE}"]


def test_existing_output_fails_before_key_and_call_and_keeps_the_file(tmp_path):
    fake = replying(GOOD)
    out = tmp_path / "beats.json"
    out.write_text("keep me")
    code, err, _ = run(tmp_path, fake, env={}, out=out)
    assert code == 1
    assert out.read_text() == "keep me"
    assert fake.keys == [] and fake.requests == []
    lines = err.splitlines()
    assert len(lines) == 1 and lines[0].startswith(PREFIX + "FAIL ")
    assert lines[0].endswith("(beats never overwrites)")
    assert "OPENROUTER_API_KEY" not in err


def test_dangling_symlink_out_is_refused_before_the_call(tmp_path):
    fake = replying(GOOD)
    out = tmp_path / "link.json"
    out.symlink_to(tmp_path / "nowhere.json")
    code, err, _ = run(tmp_path, fake, env={}, out=out)
    assert code == 1
    assert fake.keys == [] and fake.requests == []
    assert err.splitlines()[0].endswith("(beats never overwrites)")
    assert not (tmp_path / "nowhere.json").exists()


@pytest.mark.parametrize("name", ["", "   ", "dir/"], ids=["blank", "spaces", "trailing-separator"])
def test_bad_out_names_fail_before_the_call(tmp_path, name):
    fake = replying(GOOD)
    err_io, std = io.StringIO(), io.StringIO()
    script = tmp_path / "s.md"
    script.write_bytes(SCRIPT)
    code = run_beats(script, name, "synthetic/model", {"OPENROUTER_API_KEY": KEY},
                     tmp_path / "dotenv", fake.factory, err_io, std)
    assert code == 1
    assert fake.keys == [] and fake.requests == []
    lines = err_io.getvalue().splitlines()
    assert len(lines) == 1 and lines[0].startswith(PREFIX + "FAIL ")


def test_missing_parent_fails_before_the_call(tmp_path):
    fake = replying(GOOD)
    code, err, _ = run(tmp_path, fake, out=tmp_path / "nodir" / "beats.json")
    assert code == 1
    assert fake.keys == [] and fake.requests == []
    assert err.splitlines()[0].startswith(PREFIX + "FAIL ")


def test_missing_key_names_only_the_variable(tmp_path):
    fake = replying(GOOD)
    code, err, out = run(tmp_path, fake, env={})
    assert code == 1
    lines = err.splitlines()
    assert len(lines) == 1 and lines[0].startswith(f"{PREFIX}FAIL Missing: OPENROUTER_API_KEY")
    assert fake.keys == [] and not out.exists()


def test_blank_key_counts_as_unset(tmp_path):
    fake = replying(GOOD)
    code, err, _ = run(tmp_path, fake, env={"OPENROUTER_API_KEY": "   "})
    assert code == 1
    lines = err.splitlines()
    assert len(lines) == 1 and lines[0].startswith(f"{PREFIX}FAIL Missing: OPENROUTER_API_KEY")
    assert fake.keys == []


def test_dotenv_key_is_used_when_the_environment_has_none(tmp_path):
    dotenv = tmp_path / "dotenv"
    dotenv.write_text("OPENROUTER_API_KEY=from-the-file\n")
    fake = replying(GOOD)
    code, _, _ = run(tmp_path, fake, env={}, dotenv=dotenv)
    assert code == 0
    assert fake.keys == ["from-the-file"]


def test_environment_key_wins_over_dotenv(tmp_path):
    dotenv = tmp_path / "dotenv"
    dotenv.write_text("OPENROUTER_API_KEY=from-the-file\n")
    fake = replying(GOOD)
    code, _, _ = run(tmp_path, fake, dotenv=dotenv)
    assert code == 0
    assert fake.keys == [KEY]
