"""What runs when an exercise is asked for: the generator and the checks a variant is held to.

The other half of the builds. A build turns raw documents into the four artifacts of
`artifacts/`; the generation consumes them, with the tagger (`exemplars_bank/tagging.py`) and
the two screens over the free text (`functionalities/shared/screening/`). All of them take
OBJECTS and return data: not one knows what a `Workspace` is, and not one writes a file. That is `api/`'s
job, and it is what lets every component here be exercised with recorded model answers instead
of a GPU.

Deliberately free of imports and of code, like `utils`, but for a plainer reason: numpy is
44 MB of the library's 57 and only what reaches `retrieval/` needs it, so a re-export here
would pull the index into every caller that only wanted `checks`.
"""
