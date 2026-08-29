"""Infrastructure that knows nothing about the subject: engines, paths, progress, JSON.

Deliberately free of imports and of code. `inference` imports `config`, which imports
`settings`, which imports `core.paths`: anything placed here closes that into a cycle.
"""
