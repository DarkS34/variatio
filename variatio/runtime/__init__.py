"""What runs when an exercise is asked for: the components that read the artifacts.

The other half of `builders/`. A builder turns raw documents into the four artifacts of
`artifacts/`; everything here consumes them — the generator, the tagger, the two
screens over the free text and the checks a variant is held to. All of them take OBJECTS and
return data: not one knows what a `Workspace` is, and not one writes a file. That is `api/`'s
job, and it is what lets every component here be exercised with recorded model answers instead
of a GPU.

Deliberately free of imports and of code, like `utils`, but for a plainer reason: numpy is
44 MB of the runtime's 57 and only what reaches `retrieval/` needs it, so a re-export here
would pull the index into the fifteen callers that only wanted `screening`.
"""
