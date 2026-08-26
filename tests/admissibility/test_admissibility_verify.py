from variatio import admissibility


def test_accept_takes_a_valid_slot(owners_for):
    entry = {"text": "que vaya de una panadería", "slot": "ambito", "owner": None, "term": None}
    request = admissibility._accept(entry, owners_for(), {"Recursividad"})
    assert request is not None
    assert request.slot == "ambito"
    assert request.owner is None


def test_accept_takes_a_real_owner_with_a_real_term(owners_for):
    entry = {"text": "muy difícil", "slot": None, "owner": "field:nivel_dificultad", "term": "avanzado"}
    request = admissibility._accept(entry, owners_for(), {"Recursividad"})
    assert request is not None
    assert request.owner.key == "field:nivel_dificultad"
    assert request.term == "avanzado"


def test_accept_rejects_a_term_the_owner_does_not_have(owners_for):
    entry = {"text": "que use punteros", "slot": None, "owner": "concepts", "term": "Punteros"}
    assert admissibility._accept(entry, owners_for(), {"Recursividad"}) is None


def test_accept_rejects_a_term_that_is_a_target_concept(owners_for):
    entry = {"text": "que practique recursividad", "slot": None, "owner": "concepts", "term": "Recursividad"}
    assert admissibility._accept(entry, owners_for(), {"Recursividad"}) is None


def test_accept_tolerates_an_accent_difference_in_the_term(owners_for):
    entry = {"text": "que use funciones", "slot": None, "owner": "concepts", "term": "funcion"}
    request = admissibility._accept(entry, owners_for(), {"Recursividad"})
    assert request is not None
    assert request.term == "Función"


def test_accept_rejects_an_unknown_slot(owners_for):
    entry = {"text": "algo", "slot": "inventado", "owner": None, "term": None}
    assert admissibility._accept(entry, owners_for(), {"Recursividad"}) is None


def test_ruling_is_blocked_when_any_request_has_an_owner():
    owner = admissibility.Owner(key="concepts", label="l", where="w", terms=("Variable",))
    ruling = admissibility.Ruling(
        requests=(
            admissibility.Request(text="a", slot="ambito", owner=None, term=None),
            admissibility.Request(text="b", slot=None, owner=owner, term="Variable"),
        ),
        checked=True,
    )
    assert not ruling.ok
    assert len(ruling.blocked) == 1
    assert ruling.blocked[0].term == "Variable"


def test_an_empty_ruling_is_ok():
    assert admissibility.Ruling(requests=(), checked=False).ok
