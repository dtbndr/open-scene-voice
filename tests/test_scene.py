import dataclasses

import pytest

from scenevoice.validation.scene import Scene


def test_scene_holds_fields():
    scene = Scene(ordinal=1, title="Arrival", body="Hi.\n", line=3)
    assert (scene.ordinal, scene.title, scene.body, scene.line) == (1, "Arrival", "Hi.\n", 3)


def test_scene_is_frozen():
    scene = Scene(1, "Arrival", "Hi.\n", 3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scene.title = "Other"  # type: ignore[misc]


def test_scenes_with_equal_fields_are_equal():
    assert Scene(1, "A", "b\n", 2) == Scene(1, "A", "b\n", 2)
    assert Scene(1, "A", "b\n", 2) != Scene(2, "A", "b\n", 2)
