"""Read and write alarm journals in the Ignition 8.1 table layout.

Ignition's database alarm journal uses two tables (default names shown;
both are configurable on the journal profile):

  alarm_events      one row per transition: active, clear, ack
                    (and, from 8.1.8, enabled and disabled)
  alarm_event_data  properties captured with each transition, keyed by
                    the alarm_events.id of the row they belong to

This module reads either a SQLite copy of those tables or CSV exports of
them, and writes the same layout for the synthetic generator.
"""
from __future__ import annotations

import csv
import os
import shutil
import sqlite3
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# listing: event_constants
# alarm_events.eventtype
ACTIVE, CLEAR, ACK, ENABLED, DISABLED = 0, 1, 2, 4, 5

# alarm_events.eventflags bits
FLAG_SYSTEM = 1 << 0     # System Startup / System Shutdown rows
FLAG_SHELVED = 1 << 1    # alarm was shelved when the event occurred
FLAG_SYS_ACK = 1 << 2    # acknowledged by the system (live event limit)
FLAG_ACKED = 1 << 3      # already acknowledged at the time of the event
FLAG_CLEARED = 1 << 4    # already cleared at the time of the event
FLAG_ENABLED = 1 << 5    # the alarm's enabled state changed

# alarm_event_data.dtype
DT_INT, DT_FLOAT, DT_STR = 0, 1, 2
# end listing

TIME_FMT = "%Y-%m-%d %H:%M:%S.%f"

SCHEMA = """
CREATE TABLE IF NOT EXISTS alarm_events (
    id          INTEGER PRIMARY KEY,
    eventid     TEXT,
    source      TEXT,
    displaypath TEXT,
    priority    INTEGER,
    eventtype   INTEGER,
    eventflags  INTEGER,
    eventtime   TEXT
);
CREATE TABLE IF NOT EXISTS alarm_event_data (
    id          INTEGER,
    propname    TEXT,
    dtype       INTEGER,
    intvalue    INTEGER,
    floatvalue  REAL,
    strvalue    TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_time ON alarm_events (eventtime);
CREATE INDEX IF NOT EXISTS ix_events_eventid ON alarm_events (eventid);
CREATE INDEX IF NOT EXISTS ix_data_id ON alarm_event_data (id);
"""


# listing: event_record
@dataclass(frozen=True, slots=True)
class Event:
    id: int
    eventid: str
    source: str
    displaypath: str
    priority: int
    eventtype: int
    eventflags: int
    eventtime: datetime

    @property
    def is_system(self) -> bool:
        return bool(self.eventflags & FLAG_SYSTEM)

    @property
    def is_shelved(self) -> bool:
        return bool(self.eventflags & FLAG_SHELVED)
# end listing


def parse_time(text: str) -> datetime:
    """Accept the timestamp shapes SQL Server, MySQL, and Postgres export."""
    text = text.strip().replace("T", " ")
    if "+" in text[19:]:
        text = text[: 19 + text[19:].index("+")]
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognized timestamp: {text!r}")


def format_time(t: datetime) -> str:
    return t.strftime(TIME_FMT)[:-3]  # milliseconds, as Ignition stores them


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    """Open a journal read-only without taking file locks.

    immutable=1 tells SQLite the file will not change while it is open, so
    it never locks, which is what stalls on a network share. The path is
    made absolute but not resolved, so a mapped drive letter stays a drive
    letter; if the URI form is refused (a UNC path), open it plainly.
    """
    p = os.path.abspath(path)
    try:
        url = urllib.request.pathname2url(p)
        if not url.startswith("//"):
            url = "///" + url.lstrip("/")
        return sqlite3.connect(f"file:{url}?mode=ro&immutable=1", uri=True)
    except sqlite3.OperationalError:
        return sqlite3.connect(p)


# listing: load_events
def load_events(path: str | Path, table: str = "alarm_events") -> list[Event]:
    """Load alarm_events rows from a SQLite file or a CSV export.

    Rows come back sorted by time, then id, which is the order the
    gateway wrote them.
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        rows = _read_csv(path)
    else:
        with connect_readonly(path) as con:
            cur = con.execute(
                f"SELECT id, eventid, source, displaypath, priority, eventtype, "
                f"eventflags, eventtime FROM {table}")
            rows = [dict(zip(("id", "eventid", "source", "displaypath", "priority",
                              "eventtype", "eventflags", "eventtime"), r))
                    for r in cur]
    events = [
        Event(int(r["id"]), str(r["eventid"] or ""), str(r["source"] or ""),
              str(r["displaypath"] or ""), int(r["priority"] or 0),
              int(r["eventtype"]), int(r["eventflags"] or 0),
              parse_time(str(r["eventtime"])))
        for r in rows
    ]
    events.sort(key=lambda e: (e.eventtime, e.id))
    return events
# end listing


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # exports vary in case and in "display path" vs "displaypath"
        out = []
        for row in reader:
            norm = {k.strip().lower().replace(" ", ""): v for k, v in row.items() if k}
            out.append(norm)
        return out


def load_event_data(path: str | Path, table: str = "alarm_event_data") -> dict[int, dict]:
    """Return {event row id: {propname: value}} from SQLite or CSV."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        rows = _read_csv(path)
    else:
        with connect_readonly(path) as con:
            cur = con.execute(
                f"SELECT id, propname, dtype, intvalue, floatvalue, strvalue FROM {table}")
            rows = [dict(zip(("id", "propname", "dtype", "intvalue", "floatvalue",
                              "strvalue"), r)) for r in cur]
    out: dict[int, dict] = {}
    for r in rows:
        dtype = int(r["dtype"])
        key = ("intvalue", "floatvalue", "strvalue")[dtype] if dtype in (0, 1, 2) else "strvalue"
        val = r[key]
        if val not in (None, "") and dtype == DT_INT:
            val = int(val)
        elif val not in (None, "") and dtype == DT_FLOAT:
            val = float(val)
        out.setdefault(int(r["id"]), {})[r["propname"]] = val
    return out


class JournalWriter:
    """Append rows to a SQLite journal in the Ignition layout.

    The database is built in the local temp folder and moved to `path` on
    close. SQLite locking is unreliable on network shares (SMB, NFS), and a
    build written straight to one can stall; a finished file copies fine.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        fd, tmp = tempfile.mkstemp(prefix="almetrics_", suffix=".db")
        os.close(fd)
        self.tmp = Path(tmp)
        self.tmp.unlink()
        self.con = sqlite3.connect(self.tmp)
        self.con.executescript(SCHEMA)
        self.next_id = 1
        self.events: list[tuple] = []
        self.data: list[tuple] = []

    def add(self, eventid: str, source: str, displaypath: str, priority: int,
            eventtype: int, eventflags: int, t: datetime, props: dict | None = None) -> int:
        rid = self.next_id
        self.next_id += 1
        self.events.append((rid, eventid, source, displaypath, priority, eventtype,
                            eventflags, format_time(t)))
        for name, val in (props or {}).items():
            if isinstance(val, bool) or isinstance(val, int):
                self.data.append((rid, name, DT_INT, int(val), None, None))
            elif isinstance(val, float):
                self.data.append((rid, name, DT_FLOAT, None, val, None))
            else:
                self.data.append((rid, name, DT_STR, None, None, str(val)))
        if len(self.events) >= 50_000:
            self.flush()
        return rid

    def flush(self) -> None:
        self.con.executemany("INSERT INTO alarm_events VALUES (?,?,?,?,?,?,?,?)", self.events)
        self.con.executemany("INSERT INTO alarm_event_data VALUES (?,?,?,?,?,?)", self.data)
        self.con.commit()
        self.events.clear()
        self.data.clear()

    def close(self) -> None:
        self.flush()
        self.con.close()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # a leftover rollback journal beside the target would be replayed
        # into the new file on first open; remove it with the old database
        for stale in (self.path, *(self.path.with_name(self.path.name + s)
                                   for s in ("-journal", "-wal", "-shm"))):
            if stale.exists():
                stale.unlink()
        shutil.move(str(self.tmp), str(self.path))


def export_csv(db: str | Path, outdir: str | Path) -> tuple[Path, Path]:
    """Write both tables to CSV, the shape a SQL export would have."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    with connect_readonly(db) as con:
        for table in ("alarm_events", "alarm_event_data"):
            cur = con.execute(f"SELECT * FROM {table} ORDER BY id")
            p = outdir / f"{table}.csv"
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, lineterminator="\n")
                w.writerow([d[0] for d in cur.description])
                w.writerows(cur)
            paths.append(p)
    return paths[0], paths[1]
