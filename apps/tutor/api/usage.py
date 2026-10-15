"""The tutor's daily count, kept with the free chat's (`server.conversations.usage`)."""

from server.conversations.usage import Limit

LIMIT = Limit(feature="tutor", code="tutor_daily_limit", to="al tutor")

# What a refused turn carries in `X-Error-Code`.
LIMIT_CODE = LIMIT.code

refusal = LIMIT.refusal
used_today = LIMIT.used_today
record = LIMIT.record
