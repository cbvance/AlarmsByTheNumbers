from datetime import datetime

import pytest

from almetrics.episodes import parse_journal
from almetrics.generator import evaluate, generate
from almetrics.journal import ACTIVE, load_events
from almetrics.metrics import console_metrics
from almetrics.nuisance import find_chattering
from almetrics.site import ConsoleMap
from almetrics.sites import redmesa


def test_evaluate_deadband_and_delays():
    pv = [0, 11, 9, 11, 9, 11, 0, 0, 0, 0]
    assert len(evaluate(pv, 0, True, 10, 0, 0, 0)) == 3
    one = evaluate(pv, 0, True, 10, deadband=5, on_delay=0, off_delay=0)
    assert len(one) == 1 and one[0][:2] == (1, 6)
    assert evaluate(pv, 0, True, 10, 0, on_delay=2, off_delay=0) == []


def test_site_model_is_consistent():
    site = redmesa.build()
    assert len({a.source for a in site.alarms}) == len(site.alarms)
    assert all(a.console in ("C1", "C2") for a in site.alarms)
    assert set(site.signals) <= {a.source for a in site.alarms}


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    site = redmesa.build()
    d = tmp_path_factory.mktemp("gen")
    start = datetime(2026, 1, 1)
    generate(site, d / "b.db", start, 30, (), seed=7)
    generate(site, d / "a.db", start, 30, ("all",), seed=7)
    cmap = ConsoleMap(site.consoles)
    return (parse_journal(load_events(d / "b.db"), cmap),
            parse_journal(load_events(d / "a.db"), cmap), d)


def test_deterministic(tmp_path):
    site = redmesa.build()
    for n in (1, 2):
        generate(site, tmp_path / f"{n}.db", datetime(2026, 1, 1), 3, (), seed=11)
    assert load_events(tmp_path / "1.db") == load_events(tmp_path / "2.db")


def test_as_found_is_bad_on_purpose(pair):
    before, _, _ = pair
    m = console_metrics(before)
    assert m["priority_mix"]["High"] > 50
    assert m["top10_pct"] > 60
    assert m["pct_time_in_flood"] > 1
    assert len(find_chattering(before.annunciated())) >= 5
    assert before.system and not before.orphans


def test_fixes_improve_every_headline(pair):
    before, after, _ = pair
    b, a = console_metrics(before), console_metrics(after)
    assert a["annunciated"] < b["annunciated"] / 4
    assert a["pct_time_in_flood"] < b["pct_time_in_flood"]
    assert a["priority_mix"]["High"] < 10
    assert after.toggles                      # state-based suppression is journaled


def test_real_ignition_shapes(pair):
    _, _, d = pair
    ev = load_events(d / "b.db")
    assert all(e.source.startswith("prov:default:/tag:RedMesa/") or e.is_system for e in ev)
    assert {e.eventtype for e in ev} >= {0, 1, 2}
    assert sum(1 for e in ev if e.eventtype == ACTIVE and not e.is_system) > 1000
