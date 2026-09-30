"""Nuisance alarm detection: chattering, fleeting, stale, standing.

Thresholds are parameters, not constants. Chapter 12 explains where the
defaults come from and why a site should write its own into the alarm
philosophy.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median

from .episodes import Episode, ParsedJournal


@dataclass
class ChatterStat:
    source: str
    displaypath: str
    console: str
    activations: int = 0
    bursts: int = 0  # separate runs that met the chatter rule
    max_in_window: int = 0
    in_bursts: int = 0  # activations that were part of a burst


# listing: find_chattering
def find_chattering(
    episodes: list[Episode], count: int = 3, window_s: float = 60.0
) -> dict[str, ChatterStat]:
    """Alarms that went active `count` or more times within `window_s`.

    Returns only the chattering alarms, keyed by source. A burst is a run
    of activations each within window_s of the one `count - 1` before it.
    """
    by_src: dict[str, list[Episode]] = defaultdict(list)
    for e in episodes:
        by_src[e.source].append(e)
    out: dict[str, ChatterStat] = {}
    for src, eps in by_src.items():
        times = [e.active for e in eps]
        stat = ChatterStat(src, eps[0].displaypath, eps[0].console, len(times))
        in_burst = [False] * len(times)
        lo = 0
        for hi in range(len(times)):
            while (times[hi] - times[lo]).total_seconds() > window_s:
                lo += 1
            n = hi - lo + 1
            stat.max_in_window = max(stat.max_in_window, n)
            if n >= count:
                if not any(in_burst[lo:hi]):
                    stat.bursts += 1
                for k in range(lo, hi + 1):
                    in_burst[k] = True
        stat.in_bursts = sum(in_burst)
        if stat.bursts:
            out[src] = stat
    return out


# end listing


def chatterers(
    chatter: dict[str, ChatterStat], share: float = 0.5
) -> set[str]:
    """Sources whose activations mostly came in chatter bursts."""
    return {
        s
        for s, st in chatter.items()
        if st.in_bursts >= share * st.activations
    }


# listing: find_fleeting
def find_fleeting(
    episodes: list[Episode],
    max_s: float = 5.0,
    exclude: set[str] | None = None,
) -> dict[str, int]:
    """Count activations that cleared within max_s, by source.

    Pass chatterers(...) as `exclude` so an alarm that mostly chatters is
    reported under one heading, not both.
    """
    exclude = exclude or set()
    out: dict[str, int] = defaultdict(int)
    for e in episodes:
        if e.source in exclude or e.clear is None:
            continue
        if (e.clear - e.active).total_seconds() <= max_s:
            out[e.source] += 1
    return dict(out)


# end listing


@dataclass
class StaleDay:
    day: datetime
    stale: list[Episode] = field(default_factory=list)
    standing: list[Episode] = field(default_factory=list)


# listing: stale_by_day
def stale_by_day(
    pj: ParsedJournal, console: str | None = None, stale_h: float = 24.0
) -> list[StaleDay]:
    """Snapshot at each midnight: which alarms were stale, which standing.

    Stale: active for more than stale_h at the snapshot.
    Standing: active and already acknowledged at the snapshot.
    Episodes that were active before the data starts cannot be seen; the
    first stale_h of the window undercounts, and the report says so.
    """
    eps = [
        e for e in pj.annunciated() if console is None or e.console == console
    ]
    # only episodes that span a midnight can appear in a snapshot
    eps = [
        e for e in eps if e.clear is None or e.clear.date() > e.active.date()
    ]
    day0 = datetime(pj.start.year, pj.start.month, pj.start.day) + timedelta(
        days=1
    )
    out = []
    d = day0
    while d <= pj.end:
        snap = StaleDay(d)
        for e in eps:
            if e.active > d:
                break
            if e.clear is not None and e.clear <= d:
                continue
            if (d - e.active).total_seconds() > stale_h * 3600:
                snap.stale.append(e)
            if e.ack is not None and e.ack <= d:
                snap.standing.append(e)
        out.append(snap)
        d += timedelta(days=1)
    return out


# end listing


def stale_summary(days: list[StaleDay]) -> dict:
    counts = [len(d.stale) for d in days]
    names: dict[str, float] = {}
    for d in days:
        for e in d.stale:
            age = (d.day - e.active).total_seconds() / 86400
            names[e.displaypath] = max(names.get(e.displaypath, 0), age)
    return {
        "days": len(days),
        "max_stale": max(counts) if counts else 0,
        "mean_stale": sum(counts) / len(counts) if counts else 0.0,
        "days_over_5": sum(1 for c in counts if c >= 5),
        "mean_standing": (
            (sum(len(d.standing) for d in days) / len(days)) if days else 0.0
        ),
        "longest": sorted(names.items(), key=lambda kv: -kv[1]),
    }


def durations(episodes: list[Episode], end: datetime) -> list[float]:
    return [e.duration(end) for e in episodes]


def median_or_none(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return median(xs) if xs else None
