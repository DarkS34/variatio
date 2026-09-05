"""What runs when an exercise is asked for: the components that read the artifacts.

The other half of `builders/`. A builder turns raw documents into the four artifacts of
`instance/`; everything here consumes them — the generator, the tagger and its index, the
two screens over the free text, the checks a variant is held to, and the taggability review
that decides which concepts are any use as a label. All of them take OBJECTS and return
data: not one knows what a `Workspace` is, and not one writes a file. That is
`entrypoints/`'s job, and it is what lets every component here be exercised with recorded
model answers instead of a GPU.

Deliberately free of imports and of code, like `core`, but for a plainer reason: numpy is
44 MB of the runtime's 57 and only `embedder` needs it, so a re-export here would pull the
index into the fifteen callers that only wanted `screening`.
"""
