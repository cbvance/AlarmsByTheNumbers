"""Before and after: the report that proves the work paid off."""

from __future__ import annotations

from .episodes import ParsedJournal
from .metrics import Targets, console_metrics
from .nuisance import find_chattering, stale_by_day, stale_summary

ROWS = [
    # key, label, target text, lower is better
    ("per_day", "Annunciated per day", None, True),
    ("per_10min", "Average per 10 min", "1 to 2", True),
    ("max_10min", "Peak in 10 min", "10 or fewer", True),
    ("pct_10min_over", "10-min periods over 10 (%)", "under 1", True),
    ("pct_time_in_flood", "Time in flood (%)", "under 1", True),
    ("top10_pct", "Top ten share (%)", "1 to 5", True),
    ("high_pct", "High and Critical share (%)", "about 5", True),
    ("chattering", "Chattering alarms", "0", True),
    ("max_stale", "Most stale alarms on a day", "under 5", True),
]


def _extra(pj: ParsedJournal, console: str | None) -> dict:
    eps = [
        e for e in pj.annunciated() if console is None or e.console == console
    ]
    st = stale_summary(stale_by_day(pj, console))
    return {
        "chattering": len(find_chattering(eps)),
        "max_stale": st["max_stale"],
    }


# listing: compare
def compare(
    before: ParsedJournal,
    after: ParsedJournal,
    console: str | None = None,
    targets: Targets = Targets(),
) -> list[dict]:
    b = console_metrics(before, console, targets=targets) | _extra(
        before, console
    )
    a = console_metrics(after, console, targets=targets) | _extra(
        after, console
    )
    b["high_pct"], a["high_pct"] = (
        b["priority_mix"]["High"],
        a["priority_mix"]["High"],
    )
    out = []
    for key, label, target, _ in ROWS:
        bv, av = float(b[key]), float(a[key])
        change = (100.0 * (av - bv) / bv) if bv else 0.0
        out.append(
            {
                "metric": label,
                "before": bv,
                "after": av,
                "change_pct": change,
                "target": target or "",
            }
        )
    return out


# end listing
