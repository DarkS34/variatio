from variatio.functionalities.shared import screening
from variatio.functionalities.shared.screening import admissibility


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


def test_accept_rejects_the_type_already_chosen_as_a_trespass(owners_for):
    entry = {"text": "un análisis breve", "slot": None, "owner": "item_type", "term": "Análisis de código"}
    assert admissibility._accept(entry, owners_for(item_type="analisis"), {"Recursividad"}) is None


def test_accept_takes_an_undeclared_type_under_its_own_term(owners_for):
    entry = {"text": "que sea de desarrollo", "slot": None, "owner": "item_type", "term": "otra modalidad"}
    request = admissibility._accept(entry, owners_for(item_type="analisis"), {"Recursividad"})
    assert request is not None and request.term == "otra modalidad"


def test_accept_tolerates_an_accent_difference_in_the_term(owners_for):
    entry = {"text": "que use funciones", "slot": None, "owner": "concepts", "term": "funcion"}
    request = admissibility._accept(entry, owners_for(), {"Recursividad"})
    assert request is not None
    assert request.term == "Función"


def test_accept_rejects_an_unknown_slot(owners_for):
    entry = {"text": "algo", "slot": "inventado", "owner": None, "term": None}
    assert admissibility._accept(entry, owners_for(), {"Recursividad"}) is None


def test_ruling_is_blocked_when_any_request_has_an_owner():
    owner = screening.Owner(key="concepts", label="l", where="w", terms=("Variable",))
    ruling = screening.Ruling(
        requests=(
            screening.Request(text="a", slot="ambito", owner=None, term=None),
            screening.Request(text="b", slot=None, owner=owner, term="Variable"),
        ),
        checked=True,
    )
    assert not ruling.ok
    assert len(ruling.blocked) == 1
    assert ruling.blocked[0].term == "Variable"


def test_an_empty_ruling_is_ok():
    assert screening.Ruling(requests=(), checked=False).ok
