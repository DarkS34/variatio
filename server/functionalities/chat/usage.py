"""The free chat's daily count, kept beside the tutor's (`server.functionalities.shared.conversations.usage`)."""

from server.functionalities.shared.conversations.usage import Limit

LIMIT = Limit(feature="chat", code="chat_daily_limit", to="al chat libre")
