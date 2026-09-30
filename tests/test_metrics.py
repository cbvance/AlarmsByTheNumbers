from datetime import timedelta

from almetrics.episodes import parse_journal
from almetrics.floods import find_floods, flood_summary, floods_for
from almetrics.metrics import (
    console_metrics,
    priority_bucket,
    ten_minute_counts,
)
from conftest import SRC, SRC2, T0


def test_ten_minute_buckets():
    times = [T0 + timedelta(minutes=m) for m in (0, 1, 9.9, 10, 25)]
    assert ten_minute_counts(times, T0, T0 + timedelta(minutes=30)) == [
        3,
        1,
        1,
    ]


def test_flood_starts_above_10_and_ends_below_5():
    times = [
        T0 + timedelta(minutes=20, seconds=10 * i) for i in range(30)
    ]  # 30 in 5 min
    fl = find_floods(times, T0, T0 + timedelta(hours=2))
    assert len(fl) == 1
    f = fl[0]
    assert f.count == 30 and f.peak_10min == 30
    assert f.start <= times[0] and f.end > times[-1]


def test_no_flood_at_exactly_10():
    times = [T0 + timedelta(minutes=i) for i in range(10)]
    assert find_floods(times, T0, T0 + timedelta(hours=1)) == []


def test_console_metrics_and_mix(builder):
    for i in range(20):
        builder.cycle(f"a{i}", SRC, 60 + i * 5, 60 + i * 5 + 2, priority=3)
    for i in range(5):
        builder.cycle(
            f"b{i}", SRC2, 3000 + i * 600, 3001 + i * 600, priority=1
        )
    builder.cycle("end", SRC2, 86400, 86401, priority=1)
    pj = parse_journal(builder.events())
    m = console_metrics(pj)
    assert m["annunciated"] == 26
    assert m["max_10min"] == 20 and m["floods"] == 1
    assert m["priority_mix"]["High"] == round(100 * 20 / 26, 1)
    assert m["top10_pct"] == 100.0
    fl = floods_for(pj)
    assert flood_summary(fl[0])["first_out"] == "alm:H"


def test_priority_buckets():
    assert [priority_bucket(p) for p in range(5)] == [
        "Low",
        "Low",
        "Medium",
        "High",
        "High",
    ]


def test_by_month_splits_and_sums(builder):
    from almetrics.metrics import by_month

    day = 86400
    for i, s in enumerate((0, 10 * day, 40 * day, 45 * day, 70 * day)):
        builder.cycle(f"m{i}", SRC, s, s + 5)
    pj = parse_journal(builder.events())
    rows = by_month(pj)
    assert [r["month"] for r in rows] == ["2026-01", "2026-02", "2026-03"]
    assert [r["annunciated"] for r in rows] == [2, 2, 1]
