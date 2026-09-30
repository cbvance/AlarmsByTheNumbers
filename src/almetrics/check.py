"""Check an exported journal before measuring it.

Answers the questions that decide whether the numbers can be trusted:
what span the data covers, where it has holes, where the gateway
restarted, whether time ever runs backward (a clock change or a
daylight-saving fall-back in a journal stored in local time), and what
the journal profile appears to have been set to store.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .journal import ACK, ACTIVE, CLEAR, DISABLED, ENABLED, FLAG_SHELVED, Event


@dataclass
class CheckReport:
    rows: int
    start: datetime | None
    end: datetime | None
    by_type: dict[str, int]
    restarts: list[datetime] = field(default_factory=list)
    longest_gap: tuple[datetime, datetime] | None = None
    empty_days: list[datetime] = field(default_factory=list)
    backward_steps: list[tuple[int, datetime, datetime]] = field(
        default_factory=list
    )
    orphan_rows: int = 0
    shelved_rows: int = 0
    toggle_rows: int = 0
    findings: list[str] = field(default_factory=list)


# listing: check_journal
def check_journal(events: list[Event], gap_hours: float = 6.0) -> CheckReport:
    """Inspect raw rows (any order) and report on coverage and quality."""
    names = {
        ACTIVE: "active",
        CLEAR: "clear",
        ACK: "ack",
        ENABLED: "enabled",
        DISABLED: "disabled",
    }
    by_time = sorted(events, key=lambda e: (e.eventtime, e.id))
    rep = CheckReport(
        len(events),
        by_time[0].eventtime if events else None,
        by_time[-1].eventtime if events else None,
        dict(
            Counter(names.get(e.eventtype, str(e.eventtype)) for e in events)
        ),
    )
    rep.restarts = [
        e.eventtime for e in by_time if e.is_system and "Startup" in e.source
    ]
    rep.shelved_rows = sum(1 for e in events if e.eventflags & FLAG_SHELVED)
    rep.toggle_rows = sum(
        1 for e in events if e.eventtype in (ENABLED, DISABLED)
    )

    # ids are assigned as rows are written, so time should not run backward
    by_id = sorted(events, key=lambda e: e.id)
    for prev, cur in zip(by_id, by_id[1:]):
        if cur.eventtime < prev.eventtime - timedelta(minutes=5):
            rep.backward_steps.append((cur.id, prev.eventtime, cur.eventtime))

    # holes: the longest stretch with no rows, and whole days with none
    if len(by_time) > 1:
        gaps = [
            (b.eventtime - a.eventtime, a.eventtime, b.eventtime)
            for a, b in zip(by_time, by_time[1:])
        ]
        g = max(gaps)
        if g[0] >= timedelta(hours=gap_hours):
            rep.longest_gap = (g[1], g[2])
        days = {e.eventtime.date() for e in by_time}
        d = rep.start.date()
        while d <= rep.end.date():
            if d not in days:
                rep.empty_days.append(datetime(d.year, d.month, d.day))
            d += timedelta(days=1)

    # clears or acks whose episode never went active in this data
    active_ids = {e.eventid for e in events if e.eventtype == ACTIVE}
    rep.orphan_rows = sum(
        1
        for e in events
        if e.eventtype in (CLEAR, ACK)
        and not e.is_system
        and e.eventid not in active_ids
    )

    f = rep.findings
    f.append(
        f"{rep.rows:,} rows from {rep.start:%Y-%m-%d %H:%M}"
        f" to {rep.end:%Y-%m-%d %H:%M}"
    )
    f.append(
        f"{len(rep.restarts)} gateway startup(s)"
        + (
            ": " + ", ".join(f"{t:%Y-%m-%d %H:%M}" for t in rep.restarts)
            if rep.restarts
            else ""
        )
    )
    if rep.longest_gap:
        a, b = rep.longest_gap
        f.append(
            f"longest gap {b - a} from {a:%Y-%m-%d %H:%M}:"
            " check for an outage or a lost export"
        )
    if rep.empty_days:
        f.append(f"{len(rep.empty_days)} day(s) with no rows at all")
    if rep.backward_steps:
        f.append(
            f"time runs backward {len(rep.backward_steps)} time(s)"
            " in id order: "
            "clock change or daylight-saving fall-back; see Chapter 7"
        )
    f.append(
        f"{rep.orphan_rows:,} clear/ack rows with no active row"
        " (restarts, or data cut at the start)"
    )
    f.append(
        "shelved events: "
        + (
            f"present ({rep.shelved_rows:,} rows), Store Shelved Events is on"
            if rep.shelved_rows
            else "none; Store Shelved Events may be off"
        )
    )
    f.append(
        "enable/disable events: "
        + (
            f"present ({rep.toggle_rows:,} rows)"
            if rep.toggle_rows
            else "none; Store Enabled & Disabled Events may be off"
        )
    )
    return rep


# end listing
