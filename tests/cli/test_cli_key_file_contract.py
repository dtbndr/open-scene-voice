"""One contract for the per-user key file across align, beats and synth (WS37); fakes, no network.

Wiring rows live in CMDS (one `Cmd` per command); the owner-approved key-file strings are pinned
exactly here once per command. Resolution rules (precedence, parsing, permissions) are owned by
tests/synth/test_resolve_env_key_file.py and tests/keys/test_read_key_file.py.
"""

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from align_run_helper import HELLO, Fake, NoTerminal, body, pack_dir
from keys_helper import CANARY, posix_only
from wav_helper import wav_audio

from scenevoice.align import TranscriptionError
from scenevoice.cli.main import main
from scenevoice.openrouter import ChatError
from scenevoice.plan import serialize_plan
from scenevoice.synth import ENV_NAMES
from scenevoice.synth.provider import ProviderError
from scenevoice.validation import load_scenes

OTHER = "made-up-key-for-tests-0001"
OR_KEY = "OPENROUTER_API_KEY"
VX_KEY = "VERTEX_AUTHORIZATION_KEY"
GOOD = {"scenes": [{"scene": 1, "beats": [{"first": 1, "last": 1, "note": "wide"}]}]}
OR_MISSING = f'Missing: {OR_KEY}. Add it with "scenevoice keys set {OR_KEY}", or put it in {{path}}.'
VX_MISSING = (
    "Missing: GOOGLE_CLOUD_LOCATION, VERTEX_AUTHORIZATION_KEY. "
    'Add them with "scenevoice keys set GOOGLE_CLOUD_LOCATION", or put them in {path}.'
)


def chat_factory(seen: list, outcome):
    def factory(key):
        seen.append(key)

        def chat(request):
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        return chat

    return factory


def run_align(tmp_path: Path, fail: bool):
    plan, out, _ = pack_dir(tmp_path, ["Hello there."])
    fake = Fake([TranscriptionError(401, f"bad key {CANARY}") if fail else body(HELLO)])
    seen: list = []
    return main(["align", str(plan), str(out)], transcriber_factory=lambda k: (seen.append(k), fake)[1]), seen


def run_beats(tmp_path: Path, fail: bool):
    (tmp_path / "s.md").write_text("## A\nHello there.\n", encoding="utf-8")
    reply = {"choices": [{"index": 0, "finish_reason": "stop", "message": {"content": json.dumps(GOOD)}}]}
    seen: list = []
    outcome = ChatError(400, f"bad key {CANARY}") if fail else json.dumps(reply).encode()
    argv = ["beats", "s.md", "--model", "m", "--out", "b.json"]
    return main(argv, beats_factory=chat_factory(seen, outcome)), seen


def run_synth(tmp_path: Path, fail: bool):
    (tmp_path / "plan.json").write_bytes(serialize_plan(load_scenes(b"## One\n\nHello there.\n")).encode("utf-8"))
    seen: list = []

    def factory(env, model):
        seen.append(env[VX_KEY])
        if fail:
            raise ProviderError(f"HTTP 401 for key {CANARY}")
        return lambda request: wav_audio(5)

    argv = ["synth", "plan.json", "--out", str(tmp_path / "out"), "--voice", "Charon", "--model", "gemini-3.8-flash-tts"]
    return main(argv, provider_factory=factory), seen


@dataclass(frozen=True)
class Cmd:
    name: str
    cred: str  # the credential the fake receives
    text: Callable[[str], str]  # key file text holding every name the command needs
    partial: str | None  # key file text that leaves names missing (None: no key file)
    missing: str  # exact missing-key sentence, `{path}` is the key file
    run: Callable[[Path, bool], tuple[int, list]]
    escapes: bool = True  # stderr shows a non-ASCII path as backslash escapes (synth does not today)

    @property
    def prefix(self) -> str:
        return f"scenevoice {self.name}: "


def _or(value: str) -> str:
    return f"{OR_KEY}={value}\n"


def _vx(value: str) -> str:
    return f"GOOGLE_CLOUD_PROJECT=proj\nGOOGLE_CLOUD_LOCATION=us\n{VX_KEY}={value}\n"


CMDS = [
    Cmd("align", OR_KEY, _or, None, OR_MISSING, run_align),
    Cmd("beats", OR_KEY, _or, None, OR_MISSING, run_beats),
    Cmd("synth", VX_KEY, _vx, "GOOGLE_CLOUD_PROJECT=only-this\n", VX_MISSING, run_synth, escapes=False),
]


@pytest.fixture(params=CMDS, ids=lambda c: c.name)
def cmd(request) -> Cmd:
    return request.param


@pytest.fixture
def bare(clean_env, monkeypatch):
    for name in (*ENV_NAMES, "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "stdin", NoTerminal())


pytestmark = pytest.mark.usefixtures("bare")


def test_key_file_supplies_the_credential(cmd, tmp_path, key_file, capsys):
    key_file(cmd.text(CANARY))
    code, seen = cmd.run(tmp_path, False)
    err = capsys.readouterr().err
    assert code == 0, err
    assert seen == [CANARY]
    assert "NOTE key file" not in err


def test_process_env_beats_key_file(cmd, tmp_path, key_file, monkeypatch):
    key_file(cmd.text(CANARY))
    monkeypatch.setenv(cmd.cred, OTHER)
    code, seen = cmd.run(tmp_path, False)
    assert code == 0
    assert seen == [OTHER]


@posix_only
@pytest.mark.parametrize("name", ["keys"], ids=["ascii"])
def test_loose_key_file_prints_one_exact_note(cmd, tmp_path, key_file, capsys, name):
    path = key_file(cmd.text(CANARY), mode=0o644, name=name)
    shown = str(path).encode("ascii", "backslashreplace").decode("ascii") if cmd.escapes else str(path)
    code, _ = cmd.run(tmp_path, False)
    err = capsys.readouterr().err
    assert code == 0
    notes = [line for line in err.splitlines() if "key file" in line]
    assert notes == [f"{cmd.prefix}NOTE key file {shown} can be read by other users; run chmod 600 {shown}"]
    assert CANARY not in err


def break_malformed(path: Path) -> str:
    path.write_text(f"{OR_KEY}=ok\nthis is not a binding {CANARY}\n", encoding="utf-8")
    return f"key file {path}: line 2 is not NAME=value"


def break_directory(path: Path) -> str:
    path.unlink()
    path.mkdir()
    return f"key file {path} is not a regular file"


def break_bytes(path: Path) -> str:
    path.write_bytes(b"\xff\xfe" + CANARY.encode())
    return f"could not read key file {path}"


@pytest.mark.parametrize("breaker", [break_malformed, break_bytes])
def test_unusable_key_file_fails_with_one_exact_line(cmd, tmp_path, key_file, capsys, breaker):
    message = breaker(key_file(cmd.text(CANARY)))
    code, seen = cmd.run(tmp_path, False)
    out, err = capsys.readouterr()
    assert code == 1
    assert seen == []
    assert out == ""
    assert err == f"{cmd.prefix}FAIL {message}\n"
    assert CANARY not in err


def test_missing_key_names_the_key_file(cmd, tmp_path, key_file, capsys):
    if cmd.partial is not None:
        key_file(cmd.partial)
    code, seen = cmd.run(tmp_path, False)
    out, err = capsys.readouterr()
    assert code == 1
    assert seen == []
    assert out == ""
    assert err == f"{cmd.prefix}FAIL {cmd.missing.format(path=os.environ['SCENEVOICE_KEYS_FILE'])}\n"


def test_key_from_key_file_is_redacted(cmd, tmp_path, key_file, capsys):
    key_file(cmd.text(CANARY))
    code, seen = cmd.run(tmp_path, True)
    out, err = capsys.readouterr()
    assert code == 1
    assert seen == [CANARY]
    assert err.startswith(f"{cmd.prefix}FAIL ")
    assert CANARY not in err + out


def test_synth_reads_the_elevenlabs_name_from_the_key_file(tmp_path, key_file, capsys):
    key_file(f"ELEVENLABS_API_KEY={CANARY}\n")
    (tmp_path / "plan.json").write_bytes(serialize_plan(load_scenes(b"## One\n\nHello there.\n")).encode("utf-8"))
    seen: list = []

    def factory(env, model):
        seen.append(dict(env))
        raise ProviderError(f"HTTP 401 for key {CANARY}")

    argv = ["synth", "plan.json", "--out", "out", "--voice", "voice-id-1", "--model", "eleven_flash_v2_5"]
    assert main(argv, provider_factory=factory) == 1
    captured = capsys.readouterr()
    assert seen == [{"ELEVENLABS_API_KEY": CANARY}]
    assert "Missing:" not in captured.err
    assert CANARY not in captured.err + captured.out
