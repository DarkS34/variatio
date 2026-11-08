"""Step 3, «Banco de ejercicios»: the types of exercise, the bank, its marks and the class's reading.

    routes/          `/api/bank` and `/api/exercises` (the class's reading)
    edit.py          editing the bank: its exercises, their tags, what a re-extraction keeps
    reading.py       the bank as the class reads it, and whose eyes read it
    marks.py         who sees an exercise, and a teacher's stars
    tagging.py       the tagger's gates, and queueing it on the exercises picked
    exemplars_profile/  the types of exercise: their edits (`edit.py`) and `/api/profile`

Building the profile and the bank is the library's and a job of the chain (`pipeline/jobs.py`).
"""
