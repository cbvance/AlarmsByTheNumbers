"""Flood detection and flood composition.

A flood begins when more than `begin` alarms arrive within ten minutes
and ends when fewer than `end_below` arrive within ten minutes. The
rolling count is evaluated once a minute, which is fine enough for
reporting and keeps the method easy to check by hand.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .episodes import Episode, ParsedJournal


@dataclass
class Flood:
    start: datetime
    end: datetime
    count: int = 0
    peak_10min: int = 0
    episodes: list[Episode] = field(default_factory=list)

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0


# listing: find_floods
def find_floods(times: list[datetime], start: datetime, end: datetime,
                begin: int = 10, end_below: int = 5, window_min: int = 10) -> list[Flood]:
    """Return flood periods found in a sorted list of alarm times.

    A flood starts at the first alarm of the ten-minute window that took
    the count past `begin`, and ends at the end of the minute in which
    the rolling count fell below `end_below`.
    """
    if not times or start is None:
        return []
    n = int((end - start).total_seconds() // 60) + 1
    per_min = [0] * n
    for t in times:
        i = int((t - start).total_seconds() // 60)
        if 0 <= i < n:
            per_min[i] += 1
    floods: list[Flood] = []
    rolling = 0
    current: Flood | None = None
    for i in range(n):
        rolling += per_min[i]
        if i >= window_min:
            rolling -= per_min[i - window_min]
        t = start + timedelta(minutes=i + 1)        # end of this minute
        if current is None and rolling > begin:
            first = max(0, i - window_min + 1)       # window that tripped it
            current = Flood(start + timedelta(minutes=first), t, peak_10min=rolling)
        elif current is not None:
            current.peak_10min = max(current.peak_10min, rolling)
            if rolling < end_below:
                current.end = t
                floods.append(current)
                current = None
    if current is not None:
        current.end = end
        floods.append(current)
    for f in floods:
        inside = [t for t in times if f.start <= t < f.end]
        f.start = inside[0]                  # the first alarm, not the window edge
        f.count = len(inside)
    return floods
# end listing


def floods_for(pj: ParsedJournal, console: str | None = None, begin: int = 10,
               end_below: int = 5) -> list[Flood]:
    """Floods for one console with their episodes attached."""
    eps = [e for e in pj.annunciated() if console is None or e.console == console]
    fl = find_floods([e.active for e in eps], pj.start, pj.end, begin, end_below)
    j = 0
    for f in fl:
        while j < len(eps) and eps[j].active < f.start:
            j += 1
        k = j
        while k < len(eps) and eps[k].active < f.end:
            f.episodes.append(eps[k])
            k += 1
    return fl


# listing: flood_summary
def flood_summary(f: Flood, top: int = 5) -> dict:
    """What a flood was made of: first-out, top contributors, priorities."""
    by_src = Counter(e.displaypath for e in f.episodes)
    first = f.episodes[0] if f.episodes else None
    return {
        "start": f.start, "minutes": round(f.minutes, 1), "alarms": f.count,
        "peak_10min": f.peak_10min,
        "first_out": first.displaypath if first else "",
        "distinct": len(by_src),
        "top": by_src.most_common(top),
        "high_or_critical": sum(1 for e in f.episodes if e.priority >= 3),
    }
# end listing


def recurring(floods: list[Flood]) -> list[tuple[str, int]]:
    """Group floods by first-out alarm: the repeat offenders."""
    c = Counter(f.episodes[0].displaypath for f in floods if f.episodes)
    return c.most_common()
