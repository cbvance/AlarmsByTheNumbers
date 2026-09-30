"""Rebuild alarm episodes from alarm_events transition rows.

One episode is one active, acknowledge, clear cycle of one alarm, the
unit Ignition gives a single eventid. Every metric in the book counts or
times episodes, so this is the step everything else rests on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .journal import ACK, ACTIVE, CLEAR, DISABLED, ENABLED, Event
from .site import ConsoleMap


# listing: episode
@dataclass(slots=True)
class Episode:
    eventid: str
    source: str
    displaypath: str
    priority: int
    console: str
    active: datetime | None = None
    ack: datetime | None = None
    clear: datetime | None = None
    shelved: bool = False

    @property
    def annunciated(self) -> bool:
        """Shown to the operator: it went active and was not shelved."""
        return self.active is not None and not self.shelved

    def duration(self, end: datetime) -> float:
        """Seconds active; an alarm still active counts to `end`."""
        stop = self.clear or end
        return (stop - self.active).total_seconds() if self.active else 0.0

    def time_to_ack(self) -> float | None:
        if self.active and self.ack:
            return (self.ack - self.active).total_seconds()
        return None


# end listing


@dataclass
class Toggle:
    time: datetime
    source: str
    displaypath: str
    enabled: bool


@dataclass
class ParsedJournal:
    episodes: list[Episode]
    toggles: list[Toggle] = field(default_factory=list)
    system: list[Event] = field(default_factory=list)
    orphans: int = 0  # clear or ack with no active row in the data
    start: datetime | None = None
    end: datetime | None = None

    def annunciated(self, min_priority: int = 1) -> list[Episode]:
        return [
            e
            for e in self.episodes
            if e.annunciated and e.priority >= min_priority
        ]

    @property
    def days(self) -> float:
        if not self.start or not self.end:
            return 0.0
        return max((self.end - self.start).total_seconds() / 86400.0, 1e-9)

    def consoles(self) -> list[str]:
        return sorted({e.console for e in self.episodes})


# listing: parse_journal
def parse_journal(
    events: list[Event],
    consoles: ConsoleMap | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> ParsedJournal:
    """Group transition rows by eventid into episodes.

    Rows must be in time order (load_events returns them that way).
    System startup and shutdown rows are set aside. Enable and disable
    rows (8.1.8 and later, when the journal stores them) become toggles.
    A clear or ack whose active row fell outside the data is an orphan:
    counted, never guessed at.
    """
    consoles = consoles or ConsoleMap()
    eps: dict[str, Episode] = {}
    out = ParsedJournal(episodes=[])
    for ev in events:
        if ev.is_system:
            out.system.append(ev)
            continue
        if ev.eventtype in (ENABLED, DISABLED):
            out.toggles.append(
                Toggle(
                    ev.eventtime,
                    ev.source,
                    ev.displaypath,
                    ev.eventtype == ENABLED,
                )
            )
            continue
        ep = eps.get(ev.eventid)
        if ep is None:
            ep = Episode(
                ev.eventid,
                ev.source,
                ev.displaypath,
                ev.priority,
                consoles.console(ev.source),
            )
            eps[ev.eventid] = ep
        if ev.eventtype == ACTIVE and ep.active is None:
            ep.active = ev.eventtime
            ep.shelved = ev.is_shelved
        elif ev.eventtype == CLEAR and ep.clear is None:
            ep.clear = ev.eventtime
        elif ev.eventtype == ACK and ep.ack is None:
            ep.ack = ev.eventtime
    for ep in eps.values():
        if ep.active is None:
            out.orphans += 1
        else:
            out.episodes.append(ep)
    out.episodes.sort(key=lambda e: e.active)
    times = [e.eventtime for e in events]
    out.start = start or (min(times) if times else None)
    out.end = end or (max(times) if times else None)
    if start or end:
        out.episodes = [
            e
            for e in out.episodes
            if (not start or e.active >= start) and (not end or e.active < end)
        ]
    return out


# end listing
