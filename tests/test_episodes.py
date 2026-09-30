from almetrics.episodes import parse_journal
from almetrics.journal import CLEAR, Event
from almetrics.site import ConsoleMap
from conftest import SRC, SRC2, T0


# listing: test_one_episode
def test_cycle_becomes_one_episode(builder):
    ev = builder.cycle("a", SRC, 0, off_s=90, ack_s=30).events()
    pj = parse_journal(ev)
    (ep,) = pj.episodes
    assert ep.time_to_ack() == 30 and ep.duration(pj.end) == 90
    assert ep.annunciated


# end listing


def test_ack_after_clear_and_open_episode(builder):
    ev = (
        builder.cycle("a", SRC, 0, off_s=10, ack_s=40)
        .cycle("b", SRC, 100)
        .events()
    )
    pj = parse_journal(ev)
    a, b = pj.episodes
    assert a.clear < a.ack
    assert (
        b.clear is None and b.duration(pj.end) == 0
    )  # data ends at its own active row


# listing: test_orphan
def test_orphan_clear_counted_not_guessed(builder):
    ev = builder.cycle("a", SRC, 5, off_s=9).events()
    ev.insert(0, Event(99, "gone", SRC, "x", 3, CLEAR, 0, T0))
    pj = parse_journal(ev)
    assert pj.orphans == 1 and len(pj.episodes) == 1


# end listing


def test_shelved_not_annunciated_and_consoles(builder):
    ev = (
        builder.cycle("a", SRC, 0, 5, shelved=True)
        .cycle("b", SRC2, 1, 5)
        .events()
    )
    pj = parse_journal(
        ev, ConsoleMap({"RedMesa/Cryo": "C2", "RedMesa/Inlet": "C1"})
    )
    assert [e.console for e in pj.annunciated()] == ["C1"]
    assert pj.consoles() == ["C1", "C2"]
