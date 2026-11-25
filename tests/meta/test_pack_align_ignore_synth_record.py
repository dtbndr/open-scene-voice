"""Characterization: pack never reads DIR/synth_record.json (it ignores a malformed one); align does read it (check 5a) and fails on a malformed one."""

import io

import pytest
from align_run_helper import HELLO, Fake, body, go, pack_dir
from pack_run_helper import FakeStdin

from scenevoice.pack import run_pack

JUNK = b"\xff\xfe not json at all {"
OUTPUTS = ("scene_manifest.csv", "resolve_timeline.otio", "line_timings.json")


def make_dir(tmp_path, name, with_record):
    root = tmp_path / name
    root.mkdir()
    plan, out, _ = pack_dir(root, ["Hello there."], frames=24000)
    if with_record:
        (out / "synth_record.json").write_bytes(JUNK)
    return plan, out


def normalized(text, out):
    return text.replace(str(out), "DIR")


def do_pack(plan, out, editor):
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), out, err, editor)
    return code, normalized(err.getvalue(), out)


def do_align(plan, out, root):
    code, text, _ = go(plan, out, Fake([body(HELLO)]), root)
    return code, normalized(text, out)


def written(out):
    return {n: (out / n).read_bytes() for n in OUTPUTS if (out / n).exists()}


@pytest.mark.parametrize("editor", [None, "resolve"])
def test_pack_ignores_the_record(tmp_path, editor):
    with_plan, with_out = make_dir(tmp_path, "with", True)
    twin_plan, twin_out = make_dir(tmp_path, "twin", False)
    assert do_pack(with_plan, with_out, editor) == do_pack(twin_plan, twin_out, editor)
    twin = written(twin_out)
    assert "scene_manifest.csv" in twin  # positive control: the twin really packed
    if editor:
        assert "resolve_timeline.otio" in twin
    assert written(with_out) == twin
    assert (with_out / "synth_record.json").read_bytes() == JUNK


def test_align_fails_on_a_malformed_record(tmp_path):
    with_plan, with_out = make_dir(tmp_path, "with", True)
    twin_plan, twin_out = make_dir(tmp_path, "twin", False)
    fake = Fake([body(HELLO)])
    code, text, _ = go(with_plan, with_out, fake, tmp_path / "w")
    assert code == 1
    assert text.startswith("scenevoice align: FAIL ")
    assert "synth_record.json" in text
    assert fake.received == []  # zero calls
    assert "line_timings.json" not in written(with_out)
    assert (with_out / "synth_record.json").read_bytes() == JUNK
    twin_code, _ = do_align(twin_plan, twin_out, tmp_path / "t")
    assert twin_code == 0  # positive control: without the record the same pack aligns
    assert "line_timings.json" in written(twin_out)
