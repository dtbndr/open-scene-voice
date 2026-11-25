import io

import pytest
from align_run_helper import ENV, KEY, PREFIX, Fake, NoTerminal, body, go, pack_dir

from scenevoice.align.run_align import run_align

GOOD = body([(" Hello", 0.1), (" there.", 0.5)])


class Leaky(Exception):
    pass


FAULTS = [
    (OSError(f"disk {KEY} gone"), "OSError"),
    (ValueError(f"bad {KEY}"), "ValueError"),
    (RuntimeError(f"boom {KEY}"), "RuntimeError"),
    (Leaky(KEY), "Leaky"),
]
BAD_RETURNS = [None, {"words": []}, "text", 5]


def run(tmp_path, items):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there.", "Hello there.", "Hello there."])
    fake = Fake(items)
    code, err, _ = go(plan_path, out, fake, tmp_path)
    return code, err, fake, out


def assert_clean_stop(code, err, fake, out, line):
    assert code == 1
    assert err.splitlines() == [PREFIX + line]
    assert "Traceback" not in err
    assert KEY not in err
    assert len(fake.received) == 2
    assert not (out / "line_timings.json").exists()
    assert not list(out.glob(".write-*"))


@pytest.mark.parametrize(("fault", "name"), FAULTS)
def test_raising_transcriber_reports_class_name_only(tmp_path, fault, name):
    code, err, fake, out = run(tmp_path, [GOOD, fault, GOOD])
    assert_clean_stop(code, err, fake, out, f"FAIL scene 2: provider request failed: {name}")


@pytest.mark.parametrize("value", BAD_RETURNS, ids=lambda v: type(v).__name__)
def test_non_bytes_return_is_a_malformed_response(tmp_path, value):
    code, err, fake, out = run(tmp_path, [GOOD, value, GOOD])
    assert_clean_stop(code, err, fake, out, "FAIL scene 2: malformed response: response is not bytes")


def test_bytearray_return_is_accepted(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there."])
    code, err, _ = go(plan_path, out, Fake([bytearray(GOOD)]), tmp_path)
    assert code == 0, err
    assert (out / "line_timings.json").exists()


def test_fault_in_first_scene_makes_no_further_call_and_no_note(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Zebra yak.", "Hello there."])
    fake = Fake([OSError(KEY), GOOD])
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 1
    assert "NOTE" not in err
    assert len(fake.received) == 1
    assert err.splitlines() == [PREFIX + "FAIL scene 1: provider request failed: OSError"]


def test_exception_text_with_key_never_reaches_stderr_directly(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there."])
    err = io.StringIO()
    code = run_align(
        plan_path,
        NoTerminal(),
        ENV,
        tmp_path / "no.env",
        out,
        lambda key: Fake([ValueError(f"secret {key}")]),
        err,
    )
    assert code == 1
    assert KEY not in err.getvalue()
    assert "secret" not in err.getvalue()
