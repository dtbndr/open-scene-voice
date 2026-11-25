"""Shared setup for the run_preflight tests: plan files, the call wrapper, stdin fakes and a call-order spy."""

import io
import json
import sys

from scenevoice.synth.run_preflight import run_preflight

MODULE = "scenevoice.synth.run_preflight"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}


def plan_bytes(n=3, bodies=None, body="b"):
    scenes = [
        {"ordinal": i, "title": "t", "body": (bodies or {}).get(i, body)}
        for i in range(1, n + 1)
    ]
    return json.dumps({"scenes": scenes}).encode("utf-8")


def preflight(tmp_path, out_dir, *, scene=None, n=3, bodies=None, data=None, plan=True,
              stdin=None, env=ENV, **kw):
    path = None
    if plan:
        path = tmp_path / "plan.json"
        path.write_bytes(plan_bytes(n, bodies) if data is None else data)
    return run_preflight(path, stdin, env, tmp_path / "absent.env", out_dir, scene=scene, **kw)


def spy_calls(monkeypatch, *names):
    """Record the order in which run_preflight calls the named module-level functions."""
    module = sys.modules[MODULE]
    calls = []
    for name in names:
        real = getattr(module, name)
        monkeypatch.setattr(
            module, name, lambda *a, _n=name, _r=real, **k: calls.append(_n) or _r(*a, **k)
        )
    return calls


class FakeStdin:
    def __init__(self, data=b"", tty=False):
        self.buffer = io.BytesIO(data)
        self.tty = tty
        self.reads = 0
        real = self.buffer
        outer = self

        class Spy:
            def read(self):
                outer.reads += 1
                return real.read()

        self.buffer = Spy()

    def isatty(self):
        return self.tty
