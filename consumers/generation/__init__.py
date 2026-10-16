"""«Generar ejercicios»: the commission, as the server takes it, runs it and keeps it.

The generator itself is the library's (`variatio.runtime.generator`, reached through
`variatio.entrypoints.generate`), and the files of the exercises are the server's
(`server/generations.py`), read by the administrator's panel, the class's activity and the
tutor too. What is this function's alone is in `api/`: the author's routes, the job that runs
a commission, and the bounds a commission is admitted under.
"""
