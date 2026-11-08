"""What the artifacts are used for: one package per function, and what several of them share.

    generation/   an exercise asked for: the generator and the checks a variant is held to
    shared/       what more than one function uses: the screening of free text

A function never imports another one; what two of them need lives in `shared/`. The one
named exception is the evaluation, which measures the generation (`pyproject.toml`).

Deliberately free of imports, so importing one function never loads another.
"""
