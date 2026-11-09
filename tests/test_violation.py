import dataclasses

import pytest

from scenevoice.validation import Violation


def test_line_defaults_to_none():
    v = Violation(rule="r", message="m")
    assert v.rule == "r"
    assert v.message == "m"
    assert v.line is None


def test_line_is_kept_when_given():
    assert Violation(rule="r", message="m", line=3).line == 3


def test_violation_is_immutable():
    v = Violation(rule="r", message="m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.message = "other"
