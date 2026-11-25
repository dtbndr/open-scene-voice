"""Shared pieces of the `run_beats` runner tests: a scripted chat, the runner call, canonical sidecar."""

import importlib
import io
import json

from chat_run_helper import KEY, FakeChat

from scenevoice.beats import run_beats
from scenevoice.beats.build_sidecar import build_sidecar
from scenevoice.beats.segment_scenes import segment_scenes
from scenevoice.beats.serialise_sidecar import serialise_sidecar
from scenevoice.validation import load_scenes

PREFIX = "scenevoice beats: "
SCRIPT = b"## One\nFirst one. Second one.\n\n## Two\nThird one.\n"
GOOD = {
    "scenes": [
        {"scene": 1, "beats": [{"first": 1, "last": 2, "note": "wide"}]},
        {"scene": 2, "beats": [{"first": 1, "last": 1, "note": "close"}]},
    ]
}
LENGTH_LINE = "the model stopped at its length limit, so the beats may be incomplete"


def body_of(content, finish="stop"):
    return json.dumps(
        {
            "id": "synthetic-1",
            "choices": [
                {"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": content}}
            ],
        }
    ).encode()


def replying(content, finish="stop"):
    return FakeChat(body_of(content if isinstance(content, str) else json.dumps(content), finish))


def run(tmp_path, fake, script=SCRIPT, env=None, out=None, dotenv=None, script_path=None):
    script_path = script_path or tmp_path / "script.md"
    if script is not None:
        script_path.write_bytes(script)
    out = out or tmp_path / "beats.json"
    err, std = io.StringIO(), io.StringIO()
    code = run_beats(
        script_path,
        out,
        "synthetic/model",
        {"OPENROUTER_API_KEY": KEY} if env is None else env,
        dotenv or tmp_path / "dotenv",
        fake.factory,
        err,
        std,
    )
    run.stdout = std
    run.script_path = script_path
    return code, err.getvalue(), out


def canonical(script=SCRIPT, parsed=None):
    scenes = load_scenes(script)
    counts = [len(s) for s in segment_scenes(scenes)]
    return serialise_sidecar(build_sidecar(script, scenes, counts, parsed or GOOD["scenes"]))


def fail_write(monkeypatch):
    module = importlib.import_module("scenevoice.beats.run_beats")
    monkeypatch.setattr(
        module, "write_out_file", lambda path, text, **kw: f"could not write {path} (disk full)"
    )
