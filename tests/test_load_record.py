import os

import pytest

from scenevoice.synth import RECORD_NAME, RecordEntry, load_record, serialize_record
from scenevoice.validation import Violation

MALFORMED = (
    "synth_record.json is not a valid synth record "
    "(delete it to regenerate without a settings check)"
)


def _entry():
    return RecordEntry(1, "a" * 64, "Algenib", "gemini-3.8-flash-tts", "en-GB", None, None)


def test_absent_file_returns_none(tmp_path):
    assert load_record(tmp_path) is None


def test_valid_file_returns_entries(tmp_path):
    (tmp_path / RECORD_NAME).write_bytes(serialize_record((_entry(),)))
    assert load_record(tmp_path) == (_entry(),)


def test_malformed_file_returns_violation(tmp_path):
    (tmp_path / RECORD_NAME).write_bytes(b"{")
    result = load_record(tmp_path)
    assert isinstance(result, Violation)
    assert result.message == MALFORMED
    assert result.line is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_unreadable_file_returns_violation(tmp_path):
    path = tmp_path / RECORD_NAME
    path.write_bytes(serialize_record(()))
    path.chmod(0)
    try:
        result = load_record(tmp_path)
    finally:
        path.chmod(0o600)
    assert isinstance(result, Violation)
    assert result.message == MALFORMED
    assert result.line is None
