"""A reply that cannot become a sidecar is written raw and fails."""

import json

import pytest
from beats_run_helper import (
    GOOD,
    LENGTH_LINE,
    PREFIX,
    replying,
    run,
)

from scenevoice.beats import check_sidecar_shape

pytestmark = pytest.mark.usefixtures("no_sockets")


def test_coverage_failure_writes_cleaned_raw_reply_and_fails(tmp_path):
    bad = {"scenes": [GOOD["scenes"][0]]}
    raw = json.dumps(bad)
    fake = replying(raw)
    code, err, out = run(tmp_path, fake)
    assert code == 1
    assert out.read_text() == raw
    assert err.splitlines() == [f"{PREFIX}FAIL {out}: written, but scene 2 is missing from the reply"]
    assert check_sidecar_shape(json.loads(out.read_text())) is not None
    assert len(fake.requests) == 1


def test_non_json_reply_is_written_and_fails(tmp_path):
    code, err, out = run(tmp_path, replying("Sure, here you go."))
    assert code == 1
    assert out.read_text() == "Sure, here you go."
    lines = err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith(f"{PREFIX}FAIL {out}: written, but ")


def test_length_cutoff_with_broken_json_writes_raw_and_names_the_limit(tmp_path):
    raw = json.dumps(GOOD)[:40]
    code, err, out = run(tmp_path, replying(raw, finish="length"))
    assert code == 1
    assert out.read_text() == raw
    assert f"{PREFIX}FAIL {out}: written, but {LENGTH_LINE}" in err.splitlines()


def test_truncated_reply_that_passes_coverage_is_still_raw_and_fails(tmp_path):
    raw = json.dumps(GOOD)
    code, err, out = run(tmp_path, replying(raw, finish="length"))
    assert code == 1
    assert out.read_text() == raw
    assert err.splitlines() == [f"{PREFIX}FAIL {out}: written, but {LENGTH_LINE}"]
    assert check_sidecar_shape(json.loads(out.read_text())) is not None
