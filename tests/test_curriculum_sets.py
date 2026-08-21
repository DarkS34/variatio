from variant_generator.content_generator import assumed_known, forbidden

CLOSURE_UP = ["Función", "Variable"]
CLOSURE_DOWN = ["Memoización", "Recursividad"]


def test_without_curriculum_everything_upstream_is_assumed_known():
    assert assumed_known(CLOSURE_UP, None) == ["Función", "Variable"]


def test_without_curriculum_everything_downstream_is_forbidden():
    assert forbidden(CLOSURE_DOWN, None) == ["Memoización", "Recursividad"]


def test_assumed_known_INTERSECTS_the_curriculum():
    assert assumed_known(CLOSURE_UP, ["Variable", "Otro"]) == ["Variable"]


def test_forbidden_SUBTRACTS_the_curriculum():
    assert forbidden(CLOSURE_DOWN, ["Recursividad"]) == ["Memoización"]


def test_the_two_operations_are_not_the_same():
    curriculum = ["Variable"]
    assert assumed_known(CLOSURE_UP, curriculum) == ["Variable"]
    assert forbidden(CLOSURE_UP, curriculum) == ["Función"]


def test_an_empty_curriculum_is_not_a_missing_one():
    assert assumed_known(CLOSURE_UP, []) == ["Función", "Variable"]
