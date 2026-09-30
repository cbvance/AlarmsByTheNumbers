from datetime import timedelta

from almetrics.episodes import parse_journal
from almetrics.nuisance import (
    chatterers,
    find_chattering,
    find_fleeting,
    stale_by_day,
    stale_summary,
)
from conftest import SRC, SRC2


def test_chattering_rule(builder):
    for i, s in enumerate((0, 20, 40, 300, 900, 920)):
        builder.cycle(f"c{i}", SRC, s, s + 5)
    pj = parse_journal(builder.events())
    ch = find_chattering(pj.episodes, count=3, window_s=60)
    st = ch[SRC]
    assert st.bursts == 1 and st.in_bursts == 3 and st.max_in_window == 3
    assert chatterers(ch) == {SRC}  # 3 of 6 in bursts meets 0.5


def test_fleeting_excludes_chatterers(builder):
    builder.cycle("f1", SRC2, 0, 1).cycle("f2", SRC2, 500, 509).cycle(
        "f3", SRC2, 900, 902
    )
    pj = parse_journal(builder.events())
    assert find_fleeting(pj.episodes, max_s=5) == {SRC2: 2}
    assert find_fleeting(pj.episodes, max_s=5, exclude={SRC2}) == {}


def test_stale_and_standing(builder):
    day = 86400
    builder.cycle(
        "s", SRC, 3600, off_s=3 * day + 60, ack_s=3700
    )  # stale on day 2 and 3
    builder.cycle(
        "n", SRC2, day - 60, off_s=day + 60
    )  # spans midnight, not stale
    builder.cycle("z", SRC2, 4 * day, 4 * day + 1)
    pj = parse_journal(builder.events())
    days = stale_by_day(pj)
    assert [len(d.stale) for d in days] == [0, 1, 1, 0]
    assert len(days[0].standing) == 1
    s = stale_summary(days)
    assert s["max_stale"] == 1 and s["longest"][0][1] > 2
