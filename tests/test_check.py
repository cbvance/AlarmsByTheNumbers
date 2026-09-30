from datetime import timedelta

from almetrics.check import check_journal
from almetrics.journal import ACTIVE, CLEAR, FLAG_SYSTEM, Event
from conftest import SRC, T0


def ev(i, eid, etype, minutes, flags=0, src=SRC):
    return Event(
        i, eid, src, "x", 3, etype, flags, T0 + timedelta(minutes=minutes)
    )


def test_gap_restart_backward_and_orphans():
    rows = [
        ev(1, "a", ACTIVE, 0),
        ev(2, "a", CLEAR, 5),
        ev(3, "s", ACTIVE, 60 * 30, FLAG_SYSTEM, src="System Startup"),
        ev(4, "gone", CLEAR, 60 * 30 + 1),  # orphan clear after restart
        ev(5, "b", ACTIVE, 60 * 50),
        ev(6, "c", ACTIVE, 60 * 49),  # written later, stamped earlier
    ]
    rep = check_journal(rows)
    assert len(rep.restarts) == 1
    assert rep.longest_gap is not None
    assert len(rep.backward_steps) == 1
    assert rep.orphan_rows == 1
    assert any("Store Shelved Events may be off" in f for f in rep.findings)


def test_clean_journal_has_no_backward_steps():
    rows = [ev(i, f"e{i}", ACTIVE, i) for i in range(1, 50)]
    rep = check_journal(rows)
    assert rep.backward_steps == [] and rep.longest_gap is None
