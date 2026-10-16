"""Step 3, «Banco de ejercicios»: the types of exercise, the bank, its marks and the class's reading.

    routes/          `/api/bank`, `/api/exercises` (the class's reading) and `/api/profile`
    edit.py          editing the bank: its exercises, their tags, what a re-extraction keeps
    reading.py       the bank as the class reads it, and whose eyes read it
    marks.py         who sees an exercise, and a teacher's stars
    tagging.py       the tagger's gates, and queueing it on the exercises picked
    profile_edit.py  editing the types of exercise (the exemplars profile)

Building the profile and the bank is the library's and a job of the chain (`pipeline/jobs.py`).
"""
