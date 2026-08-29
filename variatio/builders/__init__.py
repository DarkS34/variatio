"""Authoring the instance artifacts from the raw documents.

A subpackage of the pipeline rather than a sibling of it: a library that cannot produce its
own inputs is unusable by anyone who does not already hold the three artifacts. It imports
the parent through relative imports and never the reverse, and `stages/build.py` is its only
importer. Docling and pypdfium2 are optional and are imported lazily inside the functions
that use them, so importing anything here must not pull in the `builders` extra.
"""
