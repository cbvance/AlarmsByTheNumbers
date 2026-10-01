"""The top-ten bad actor report.

Ranks alarms by annunciated count and attaches what a rationalization
team needs to decide what kind of problem each one is: chattering,
fleeting, standing for days, or simply frequent.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .episodes import Episode, ParsedJournal
from .nuisance import (
    chatterers,
    find_chattering,
    find_fleeting,
    median_or_none,
)
from .site import PRIORITY_NAMES


@dataclass
class BadActor:
    rank: int
    source: str
    displaypath: str
    console: str
    priority: str
    count: int
    pct: float
    cum_pct: float
    per_day: float
    chattering: bool
    fleeting: int
    median_active_s: float | None
    median_ack_s: float | None
    diagnosis: str


# listing: bad_actors
def bad_actors(
    pj: ParsedJournal,
    top: int = 10,
    console: str | None = None,
    min_priority: int = 1,
) -> list[BadActor]:
    eps = [
        e
        for e in pj.annunciated(min_priority)
        if console is None or e.console == console
    ]
    total = len(eps) or 1
    by_src: dict[str, list[Episode]] = defaultdict(list)
    for e in eps:
        by_src[e.source].append(e)
    chatter = find_chattering(eps)
    fleet = find_fleeting(eps, exclude=chatterers(chatter))
    ranked = sorted(by_src.items(), key=lambda kv: -len(kv[1]))[:top]
    out, cum = [], 0.0
    for i, (src, lst) in enumerate(ranked, 1):
        pct = 100.0 * len(lst) / total
        cum += pct
        med_act = median_or_none([e.duration(pj.end) for e in lst])
        med_ack = median_or_none([e.time_to_ack() for e in lst])
        out.append(
            BadActor(
                i,
                src,
                lst[0].displaypath,
                lst[0].console,
                PRIORITY_NAMES[lst[0].priority],
                len(lst),
                pct,
                cum,
                len(lst) / pj.days,
                src in chatter,
                fleet.get(src, 0),
                med_act,
                med_ack,
                diagnose(
                    (
                        chatter[src].in_bursts / len(lst)
                        if src in chatter
                        else 0.0
                    ),
                    fleet.get(src, 0),
                    len(lst),
                    med_act,
                ),
            )
        )
    return out


# end listing


# listing: diagnose
def diagnose(
    chatter_share: float, fleeting: int, count: int, med_active: float | None
) -> str:
    """A first guess at the fix, for the rationalization worksheet.

    chatter_share is the fraction of activations that were part of a
    chatter burst; an alarm that chattered once is still flagged in the
    chattering count, but it is not diagnosed as a chatterer.
    """
    if chatter_share >= 0.5:
        return "chatter: deadband+delay"
    if fleeting and fleeting >= count / 2:
        return "fleeting: on-delay"
    if med_active is not None and med_active > 86400:
        return "standing: state/remove"
    return "frequent: setpoint"


# end listing


# listing: what_if
def without(pj: ParsedJournal, sources: set[str]) -> ParsedJournal:
    """The same journal with some alarms' episodes taken out: what the
    metrics would be if those alarms had been fixed."""
    from dataclasses import replace

    return replace(
        pj, episodes=[e for e in pj.episodes if e.source not in sources]
    )


def what_if(
    pj: ParsedJournal, top: int = 10, console: str | None = None
) -> list[dict]:
    """Headline metrics after removing the top 0, 1, ... top bad actors."""
    from .metrics import console_metrics

    ranked = [a.source for a in bad_actors(pj, top, console)]
    rows = []
    for k in range(len(ranked) + 1):
        m = console_metrics(without(pj, set(ranked[:k])), console)
        rows.append(
            {
                "removed": k,
                "per_day": m["per_day"],
                "max_10min": m["max_10min"],
                "pct_time_in_flood": m["pct_time_in_flood"],
            }
        )
    return rows


# end listing
