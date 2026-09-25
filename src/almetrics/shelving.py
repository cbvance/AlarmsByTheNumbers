"""Shelving and suppression analysis.

What the Ignition 8.1 journal can show:
  * activations that happened while shelved, flagged in eventflags,
    but only when the profile's Store Shelved Events is enabled
    (it is off by default);
  * enable and disable transitions, from 8.1.8, only when
    Store Enabled & Disabled Events is enabled.
What it cannot show: the shelve action itself. The report says so
rather than guessing.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .episodes import ParsedJournal


@dataclass
class DisabledSpan:
    source: str
    displaypath: str
    start: datetime
    end: datetime | None     # None: still disabled at end of data

    def hours(self, data_end: datetime) -> float:
        return ((self.end or data_end) - self.start).total_seconds() / 3600


@dataclass
class ShelvingReport:
    shelved_activations: int
    shelved_by_alarm: list[tuple[str, int, float]]   # displaypath, count, share of its activations
    disabled_spans: list[DisabledSpan] = field(default_factory=list)
    state_events: int = 0            # bursts of disables that look state-based
    still_disabled: list[DisabledSpan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# listing: shelving_report
def shelving_report(pj: ParsedJournal, long_h: float = 24.0,
                    burst_s: float = 2.0, burst_n: int = 3) -> ShelvingReport:
    total = defaultdict(int)
    shelved = defaultdict(int)
    for e in pj.episodes:
        total[e.displaypath] += 1
        if e.shelved:
            shelved[e.displaypath] += 1
    rows = sorted(((k, n, n / total[k]) for k, n in shelved.items()), key=lambda r: -r[1])
    rep = ShelvingReport(sum(shelved.values()), rows)
    if not shelved:
        rep.warnings.append("No shelved activations in the data. Either nobody shelved an "
                            "alarm or Store Shelved Events is off on this journal profile.")
    if not pj.toggles:
        rep.warnings.append("No enable/disable rows. Either nothing was disabled or Store "
                            "Enabled & Disabled Events is off (it exists from 8.1.8).")
    open_: dict[str, DisabledSpan] = {}
    for tg in pj.toggles:
        if not tg.enabled and tg.source not in open_:
            open_[tg.source] = DisabledSpan(tg.source, tg.displaypath, tg.time, None)
        elif tg.enabled and tg.source in open_:
            span = open_.pop(tg.source)
            span.end = tg.time
            rep.disabled_spans.append(span)
    rep.still_disabled = list(open_.values())
    rep.disabled_spans.extend(rep.still_disabled)
    # disables that land together are a state change, not a person
    offs = sorted(t.time for t in pj.toggles if not t.enabled)
    i = 0
    while i < len(offs):
        j = i
        while j + 1 < len(offs) and offs[j + 1] - offs[i] <= timedelta(seconds=burst_s):
            j += 1
        if j - i + 1 >= burst_n:
            rep.state_events += 1
        i = j + 1
    return rep
# end listing


def long_disabled(rep: ShelvingReport, data_end: datetime, hours: float = 24.0):
    return [s for s in rep.disabled_spans if s.hours(data_end) > hours]
