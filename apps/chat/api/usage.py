"""The free chat's daily count, kept beside the tutor's (`server.conversations.usage`)."""

from server.conversations.usage import Limit

LIMIT = Limit(feature="chat", code="chat_daily_limit", to="al chat libre")
