from datetime import datetime

from almetrics.journal import (
    ACTIVE,
    FLAG_SYSTEM,
    JournalWriter,
    export_csv,
    load_event_data,
    load_events,
    parse_time,
)


def test_round_trip_sqlite_and_csv(tmp_path):
    db = tmp_path / "j.db"
    w = JournalWriter(db)
    t = datetime(2026, 3, 1, 12, 0, 0, 250000)
    w.add(
        "e1",
        "prov:default:/tag:A:/alm:H",
        "A H",
        3,
        ACTIVE,
        0,
        t,
        {"eventValue": 71.5, "ackUser": "usr:nholt", "count": 2},
    )
    w.add("s1", "System Startup", "System Startup", 0, ACTIVE, FLAG_SYSTEM, t)
    w.close()
    ev = load_events(db)
    assert [e.eventid for e in ev] == ["e1", "s1"]
    assert ev[0].eventtime == t and ev[1].is_system
    data = load_event_data(db)
    assert data[1] == {"eventValue": 71.5, "ackUser": "usr:nholt", "count": 2}
    ev_csv, data_csv = export_csv(db, tmp_path / "csv")
    assert load_events(ev_csv) == ev
    assert load_event_data(data_csv)[1]["eventValue"] == 71.5


def test_parse_time_shapes():
    want = datetime(2026, 1, 2, 3, 4, 5)
    for text in (
        "2026-01-02 03:04:05",
        "2026-01-02T03:04:05",
        "01/02/2026 03:04:05",
        "2026-01-02 03:04:05+00:00",
    ):
        assert parse_time(text) == want
    assert parse_time("2026-01-02 03:04:05.123").microsecond == 123000


def test_missing_journal_is_not_created(tmp_path):
    import pytest

    missing = tmp_path / "nope.db"
    with pytest.raises(FileNotFoundError):
        load_events(missing)
    assert not missing.exists()


def test_readers_close_their_connections(tmp_path, monkeypatch):
    """Windows cannot replace a file that is still open, so every reader
    must close its connection, not just leave it to garbage collection."""
    import sqlite3

    import almetrics.journal as j

    db = tmp_path / "j.db"
    w = JournalWriter(db)
    w.add(
        "e1",
        "prov:default:/tag:A:/alm:H",
        "A H",
        3,
        ACTIVE,
        0,
        datetime(2026, 1, 1),
        {"eventValue": 1.0},
    )
    w.close()
    opened = []
    real = sqlite3.connect

    class Tracked:
        def __init__(self, *a, **k):
            self.con = real(*a, **k)
            self.closed = False
            opened.append(self)

        def execute(self, *a):
            return self.con.execute(*a)

        def close(self):
            self.closed = True
            self.con.close()

    monkeypatch.setattr(j.sqlite3, "connect", Tracked)
    load_events(db)
    load_event_data(db)
    export_csv(db, tmp_path / "csv")
    assert opened and all(c.closed for c in opened)
