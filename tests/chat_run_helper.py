"""Shared fake chat and synthetic OpenRouter cases for the beats and openrouter tests (no network)."""

import json

from paths_helper import FIXTURES

KEY = "made-up-key-for-tests-0001"
OPENROUTER_FIXTURES = FIXTURES / "openrouter"


def synthetic(name):
    """The named case (a dict with a `body`) from the unobserved synthetic chat file."""
    doc = json.loads((OPENROUTER_FIXTURES / "chat_synthetic_cases.json").read_text(encoding="ascii"))
    return doc["cases"][name]


class FakeChat:
    """Records keys and requests; each call returns or raises the next outcome."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.keys = []
        self.requests = []

    def factory(self, key):
        self.keys.append(key)

        def chat(body):
            self.requests.append(body)
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

        return chat
