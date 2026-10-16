"""The free chat's conversations: the conversational functions' store, on `<workspace>/chat/`.

Kept exactly as the tutor's are (`server.conversations.store`): one file per conversation under
its author, written whole under a lock per file. The replies are the assistant's, and a
conversation keeps no state of its own.
"""

from server.conversations import store as shared

FOLDER = "chat"
STUDENT = shared.STUDENT
ASSISTANT = "assistant"

STORE = shared.Store(folder=FOLDER, reply_role=ASSISTANT, scope="chat")
