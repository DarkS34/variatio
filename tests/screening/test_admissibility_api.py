from variatio import screening, wording


def test_the_scope_payload_carries_slots_owners_and_facts(graph, profile, context):
    from server.routers.pipeline import _scope_payload

    payload = _scope_payload(graph, profile, context, "ejercicio", wording.of("es"))
    assert [s["key"] for s in payload["slots"]] == [s.key for s in screening.catalog()]
    assert "field:nivel_dificultad" in {o["key"] for o in payload["owners"]}
    assert {"key": "language_of_instruction", "value": "castellano"} in payload["facts"]
    assert all("terms" not in o for o in payload["owners"])
