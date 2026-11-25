"""Shared pieces of the OpenRouter transport tests: a scripted opener and the mapped error."""

import io
import urllib.error

import pytest
from chat_run_helper import KEY, OPENROUTER_FIXTURES

from scenevoice.openrouter import ChatError
from scenevoice.openrouter.chat_constants import CHAT_URL
from scenevoice.openrouter.openrouter_chat import openrouter_chat

BODY = b'{"model": "m"}'


def observed(name):
    return (OPENROUTER_FIXTURES / name).read_bytes()


class FakeResponse:
    def __init__(self, status=200, body=b"{}", read_error=None):
        self.status = status
        self._body = body
        self._read_error = read_error

    def read(self):
        if self._read_error is not None:
            raise self._read_error
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if self.raises is not None:
            raise self.raises
        return self.response


def http_error(code, body):
    return urllib.error.HTTPError(CHAT_URL, code, "x", {}, io.BytesIO(body))


def chat_error(opener):
    with pytest.raises(ChatError) as info:
        openrouter_chat(BODY, KEY, opener=opener)
    return info.value
