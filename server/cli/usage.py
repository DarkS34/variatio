"""`usage`: what a subject's jobs cost, in tokens, by kind of job and by engine.

Read off `logs/<slug>/usage.jsonl` (`server/jobs/usage_log.py`), one line per job that called
a model: the figures a page of costs is made from — what building a subject took, what a
hundred turns of the tutor take — without a database or the API running.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone


def show_usage(args) -> int:
    """Print the jobs of one subject by kind: how many, their calls, tokens in and out, and the mean."""
    from ..jobs import usage_log

    rows = usage_log.read(args.workspace)
    if args.days:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        rows = [row for row in rows if _moment(row.get("at")) and _moment(row.get("at")) >= since]
    if not rows:
        print(f"«{args.workspace}» no tiene ningún trabajo con llamadas apuntado todavía.")
        return 0

    by_kind: dict[str, dict] = defaultdict(lambda: {"jobs": 0, "calls": 0, "in": 0, "out": 0})
    by_engine: dict[str, dict] = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0})
    for row in rows:
        kind = by_kind[str(row.get("kind") or "?")]
        kind["jobs"] += 1
        for field in ("calls", "in", "out"):
            kind[field] += int(row.get(field) or 0)
        for phase in row.get("phases") or []:
            engine = by_engine[str(phase.get("engine") or "?")]
            for field in ("calls", "in", "out"):
                engine[field] += int(phase.get(field) or 0)

    print(f"Consumo de «{args.workspace}»" + (f", últimos {args.days} días" if args.days else "") + ":")
    print(f"{'trabajo':<22}{'trabajos':>9}{'llamadas':>10}{'entrada':>12}{'salida':>11}{'media ent.':>12}{'media sal.':>12}")
    for kind, totals in sorted(by_kind.items(), key=lambda pair: -(pair[1]["in"] + pair[1]["out"])):
        jobs = totals["jobs"]
        print(
            f"{kind:<22}{jobs:>9}{totals['calls']:>10}{totals['in']:>12}{totals['out']:>11}"
            f"{totals['in'] // jobs:>12}{totals['out'] // jobs:>12}"
        )
    print("Por motor:")
    for engine, totals in sorted(by_engine.items()):
        print(f"  {engine:<20}{totals['calls']:>10} llamadas{totals['in']:>12} de entrada{totals['out']:>11} de salida")
    return 0


def _moment(value) -> datetime | None:
    """Read a line's ISO moment, or None."""
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
