import scenevoice.synth as synth
from scenevoice.synth import PlanScene, neighbour_texts

THREE = [PlanScene(1, "a", "body one"), PlanScene(2, "b", "body two"), PlanScene(3, "c", "body three")]


def test_first_scene_has_no_previous():
    assert neighbour_texts(THREE, 1) == (None, "body two")


def test_middle_scene_has_both_neighbours():
    assert neighbour_texts(THREE, 2) == ("body one", "body three")


def test_last_scene_has_no_next():
    assert neighbour_texts(THREE, 3) == ("body two", None)


def test_one_scene_plan_has_no_neighbours():
    assert neighbour_texts([PlanScene(1, "a", "only")], 1) == (None, None)


def test_bodies_are_whole():
    big = "x" * 50_000
    plan = [PlanScene(1, "a", "one"), PlanScene(2, "b", big), PlanScene(3, "c", "three")]
    previous, following = neighbour_texts(plan, 1)[1], neighbour_texts(plan, 3)[0]
    assert previous == big and following == big


def test_bodies_are_verbatim():
    plan = [PlanScene(1, "a", "  lead\n"), PlanScene(2, "b", "mid"), PlanScene(3, "c", "\ttrail  ")]
    assert neighbour_texts(plan, 2) == ("  lead\n", "\ttrail  ")


def test_missing_neighbour_is_none_not_empty():
    previous, following = neighbour_texts(THREE, 1)[0], neighbour_texts(THREE, 3)[1]
    assert previous is None and following is None


def test_importable_from_package():
    assert synth.neighbour_texts is neighbour_texts
