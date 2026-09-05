from variatio import admissibility


def test_the_commission_accepts_a_ruling():
    from evaluation import Commission

    commission = Commission(
        concepts=["Recursividad"],
        item_type="ejercicio",
        instructions="que vaya de deporte",
        ruling=admissibility.Ruling(
            (admissibility.Request("que vaya de deporte", "ambito", None, None),), True
        ),
    )
    assert commission.ruling.ok


def test_the_recorded_session_never_carries_the_ruling():
    import inspect

    from evaluation import EvaluationSession

    source = inspect.getsource(EvaluationSession.to_dict)
    assert "ruling" not in source


def test_the_system_arm_reuses_the_ruling_instead_of_rescreening(monkeypatch):
    from evaluation.arms import system

    calls = []
    monkeypatch.setattr(admissibility, "screen", lambda *a, **k: calls.append(1))

    class _Generator:
        def generate(self, **kwargs):
            assert kwargs["ruling"] is not None
            return []

    class _Context:
        generator = _Generator()

    from evaluation import Commission

    commission = Commission(
        concepts=["Recursividad"],
        item_type="ejercicio",
        instructions="que vaya de deporte",
        ruling=admissibility.Ruling((), True),
    )
    system.run(commission, _Context())
    assert calls == []
