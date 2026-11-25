"""Shared helpers for the keys route tests: a canned `keys status` output and a route table over the stub."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from web_http_helper import make_request

from scenevoice.web import Request, Response, register_keys_routes

PATH = "/k/keys.env"
NAME = "OPENROUTER_API_KEY"
PROJECT = "my project\u0085x"
STATUS = {
    "path": PATH,
    "keys": {
        "GOOGLE_CLOUD_PROJECT": {"saved": True, "value": PROJECT},
        "GOOGLE_CLOUD_LOCATION": {"saved": False},
        "VERTEX_AUTHORIZATION_KEY": {"saved": False},
        "ELEVENLABS_API_KEY": {"saved": False},
        "OPENROUTER_API_KEY": {"saved": True},
    },
}
STATUS_STDOUT = json.dumps(STATUS, ensure_ascii=False) + "\n"


def routes_over(stub: Any, cwd: Path, **options: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {"cwd": cwd, "environ": {"HOME": "/h"}, "ignored_environment": []}
    return register_keys_routes(prefix=stub.prefix, **{**arguments, **options})


def call(routes: Any, method: str, path: str, body: object = None) -> Response:
    request: Request = replace(make_request(method, path), json_body=body)
    return routes[path][method](request)
