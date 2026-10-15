"""The tutor's conversations: the conversational functions' store, on `<workspace>/tutor/`.

How a conversation is kept — one file per conversation under its author, written whole under
a lock per file, `pending` naming the job a reply comes from — is shared with the free chat
and lives once in `server.conversations.store`. Here are the tutor's folder, the role its
replies are written under, and the state a new conversation starts with: the concept it
stands on and the trail it walked (`apps.tutor.focus`). The files did not move.
"""

from server.conversations import store as shared

from .. import paths

FORMAT = shared.FORMAT
AUTHOR_PREFIX = shared.AUTHOR_PREFIX
ID_PATTERN = shared.ID_PATTERN
STUDENT = shared.STUDENT
TUTOR = "tutor"

STORE = shared.Store(
    folder=paths.CONVERSATIONS_FOLDER,
    reply_role=TUTOR,
    scope="tutor",
    initial_state=lambda: {"focus": [], "trail": []},
)

lock_for = STORE.lock_for
create = STORE.create
append_tutor = STORE.append_reply
write = STORE.write
delete = STORE.delete
get = STORE.get
list_for = STORE.list_for
list_all = STORE.list_all
authors = STORE.authors
count = STORE.count
author_dir = STORE.author_dir
read_file = STORE.read_file
append_student = shared.append_student
mark_failed = shared.mark_failed
