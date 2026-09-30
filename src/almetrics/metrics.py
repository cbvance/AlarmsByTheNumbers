"""The metrics engine: alarm rates, flood time, priority mix, top ten.

All rates are per operator console, computed from annunciated episodes
(went active, not shelved) at or above a minimum priority. The targets
are the ISA-18.2 suggested values as the book cites them in Chapter 4;
keep them in one place so a site can adopt its own philosophy numbers.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from .episodes import Episode, ParsedJournal
from .floods import find_floods
from .site import PRIORITY_NAMES


# listing: targets
@dataclass(frozen=True)
class Targets:
    per_10min_acceptable: float = 1.0  # average annunciated alarms per 10 min
    per_10min_manageable: float = 2.0
    flood_begin: int = 10  # alarms in 10 min that start a flood
    flood_end: int = 5  # below this many in 10 min it ends
    pct_10min_over: float = 1.0  # percent of 10-min periods above 10
    max_in_10min: int = 10
    pct_time_in_flood: float = 1.0
    top10_pct_max: float = 5.0  # top ten share of all alarms, percent
    stale_per_day: int = 5  # alarms active > 24 h, any day
    priority_mix: tuple[float, float, float] = (
        80.0,
        15.0,
        5.0,
    )  # low, med, high


# end listing


# listing: ten_minute_counts
def ten_minute_counts(
    times: list[datetime], start: datetime, end: datetime
) -> list[int]:
    """Counts in fixed 10-minute periods from start.

    A partial period at the end is dropped, so every period is 10 minutes.
    """
    n = int((end - start).total_seconds() // 600)
    counts = [0] * max(n, 0)
    for t in times:
        i = int((t - start).total_seconds() // 600)
        if 0 <= i < n:
            counts[i] += 1
    return counts


# end listing


def daily_counts(
    times: list[datetime], start: datetime, days: int
) -> list[int]:
    day0 = datetime(start.year, start.month, start.day)
    counts = [0] * days
    for t in times:
        i = (t - day0).days
        if 0 <= i < days:
            counts[i] += 1
    return counts


def priority_bucket(p: int) -> str:
    """Collapse Ignition's five priorities into the three-way benchmark mix."""
    return {0: "Low", 1: "Low", 2: "Medium", 3: "High", 4: "High"}[p]


# listing: console_metrics
def console_metrics(
    pj: ParsedJournal,
    console: str | None = None,
    min_priority: int = 1,
    targets: Targets = Targets(),
) -> dict:
    """Headline metrics for one console (or the whole journal if None)."""
    eps = [
        e
        for e in pj.annunciated(min_priority)
        if console is None or e.console == console
    ]
    times = [e.active for e in eps]
    tens = ten_minute_counts(times, pj.start, pj.end)
    periods = len(tens) or 1
    floods = find_floods(
        times, pj.start, pj.end, targets.flood_begin, targets.flood_end
    )
    flood_s = sum((f.end - f.start).total_seconds() for f in floods)
    span_s = (pj.end - pj.start).total_seconds()
    by_pri = Counter(e.priority for e in eps)
    mix = Counter(priority_bucket(e.priority) for e in eps)
    by_src = Counter(e.source for e in eps)
    top10 = sum(n for _, n in by_src.most_common(10))
    total = len(eps)
    pct = lambda n: 100.0 * n / total if total else 0.0
    return {
        "console": console or "ALL",
        "annunciated": total,
        "days": round(pj.days, 2),
        "per_day": total / pj.days if pj.days else 0.0,
        "per_hour": total / (pj.days * 24) if pj.days else 0.0,
        "per_10min": total / periods,
        "max_10min": max(tens) if tens else 0,
        "pct_10min_over": 100.0
        * sum(1 for c in tens if c > targets.flood_begin)
        / periods,
        "floods": len(floods),
        "pct_time_in_flood": 100.0 * flood_s / span_s if span_s else 0.0,
        "priority_counts": {
            PRIORITY_NAMES[p]: by_pri.get(p, 0) for p in range(5)
        },
        "priority_mix": {
            k: round(pct(mix.get(k, 0)), 1) for k in ("Low", "Medium", "High")
        },
        "distinct_alarms": len(by_src),
        "top10_pct": pct(top10),
    }


# end listing


def all_consoles(
    pj: ParsedJournal, min_priority: int = 1, targets: Targets = Targets()
) -> list[dict]:
    return [
        console_metrics(pj, c, min_priority, targets) for c in pj.consoles()
    ]


def verdict(m: dict, t: Targets = Targets()) -> dict[str, bool]:
    """True where the metric meets its target."""
    return {
        "per_10min": m["per_10min"] <= t.per_10min_manageable,
        "pct_10min_over": m["pct_10min_over"] <= t.pct_10min_over,
        "max_10min": m["max_10min"] <= t.max_in_10min,
        "pct_time_in_flood": m["pct_time_in_flood"] <= t.pct_time_in_flood,
        "top10_pct": m["top10_pct"] <= t.top10_pct_max,
        "high_pct": m["priority_mix"]["High"] <= t.priority_mix[2] * 1.5,
    }


def as_dict(t: Targets) -> dict:
    return asdict(t)


def window(pj: ParsedJournal, start: datetime, minutes: int) -> list[Episode]:
    end = start + timedelta(minutes=minutes)
    return [e for e in pj.annunciated() if start <= e.active < end]


# listing: by_month
def slice_journal(
    pj: ParsedJournal, start: datetime, end: datetime
) -> ParsedJournal:
    """The same journal restricted to episodes that began in [start, end)."""
    eps = [e for e in pj.episodes if start <= e.active < end]
    return ParsedJournal(
        eps,
        [t for t in pj.toggles if start <= t.time < end],
        [s for s in pj.system if start <= s.eventtime < end],
        0,
        start,
        end,
    )


def by_month(
    pj: ParsedJournal, console: str | None = None, targets: Targets = Targets()
) -> list[dict]:
    """console_metrics for each calendar month in the journal."""
    out = []
    m = datetime(pj.start.year, pj.start.month, 1)
    while m < pj.end:
        nxt = datetime(m.year + (m.month == 12), m.month % 12 + 1, 1)
        part = slice_journal(pj, max(m, pj.start), min(nxt, pj.end))
        row = console_metrics(part, console, targets=targets)
        row["month"] = f"{m:%Y-%m}"
        out.append(row)
        m = nxt
    return out


# end listing
