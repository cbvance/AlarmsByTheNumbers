from openpyxl import load_workbook

from almetrics.badactors import bad_actors
from almetrics.compare import compare
from almetrics.madb import export_madb
from almetrics.shelving import shelving_report
from almetrics.sites import redmesa
from conftest import SRC
from test_generator import pair  # noqa: F401  (module fixture)


def test_bad_actors_ranked(pair):  # noqa: F811
    before, _, _ = pair
    acts = bad_actors(before)
    assert len(acts) == 10
    assert [a.count for a in acts] == sorted(
        (a.count for a in acts), reverse=True
    )
    assert acts[0].diagnosis.startswith("chatter")
    assert abs(acts[-1].cum_pct - sum(a.pct for a in acts)) < 1e-9


def test_madb_workbook(pair, tmp_path):  # noqa: F811
    before, _, _ = pair
    p = export_madb(before, tmp_path / "madb.xlsx", redmesa.build(), "b.db")
    wb = load_workbook(p)
    assert wb.sheetnames == ["MADB", "Matrix", "Lookups", "Period"]
    ws = wb["MADB"]
    header = [c.value for c in ws[1]]
    assert "Consequence" in header and "Rationalized Priority" in header
    assert ws.max_row - 1 == len(
        redmesa.build().alarms
    )  # every configured alarm listed
    f = ws.cell(2, header.index("Rationalized Priority") + 1).value
    assert f.startswith("=IF(") and "Matrix!" in f


def test_shelving_and_compare(pair):  # noqa: F811
    before, after, _ = pair
    rb, ra = shelving_report(before), shelving_report(after)
    assert rb.shelved_activations > 0 and not rb.disabled_spans
    assert ra.state_events > 0
    rows = {r["metric"]: r for r in compare(before, after)}
    assert rows["Chattering alarms"]["after"] == 0
    assert rows["Annunciated per day"]["change_pct"] < -50


def test_what_if_and_cards(pair, tmp_path):  # noqa: F811
    from almetrics.badactors import bad_actors, what_if
    from almetrics.charts import actor_card

    before, _, _ = pair
    rows = what_if(before, top=5)
    assert [r["removed"] for r in rows] == [0, 1, 2, 3, 4, 5]
    assert rows[-1]["per_day"] < rows[0]["per_day"] / 2
    a = bad_actors(before, top=1)[0]
    assert actor_card(before, a, tmp_path / "card.png").exists()


def test_shelve_periods(builder):
    from almetrics.episodes import parse_journal
    from almetrics.shelving import shelve_periods

    for i, s in enumerate((0, 600, 1200, 9000, 9100)):
        builder.cycle(f"s{i}", SRC, s, s + 5, shelved=True)
    builder.cycle("x", SRC, 20000, 20005)
    ps = shelve_periods(parse_journal(builder.events()))
    assert [p.activations for p in ps] == [3, 2]
    assert ps[0].minutes == 20.0


def fill(path, rows):
    """Write team fields into an exported MADB, as a rationalizer would."""
    from openpyxl import load_workbook

    wb = load_workbook(path)
    ws = wb["MADB"]
    header = [c.value for c in ws[1]]
    for r, values in rows.items():
        for field, v in values.items():
            ws.cell(r, header.index(field) + 1).value = v
    wb.save(path)


def test_madb_round_trip_and_check(pair, tmp_path):  # noqa: F811
    from almetrics.madb import check_madb, progress, read_madb

    before, _, _ = pair
    path = export_madb(before, tmp_path / "m.xlsx", redmesa.build())
    good = {
        "Classification": "Process",
        "Cause": "c",
        "Consequence": "x",
        "Corrective Action": "a",
        "Time to Respond": "3 to 10 min",
        "Severity": "Major",
        "Deadband": 3,
        "Keep or Remove": "Keep",
        "Rationalized By": "LM",
    }
    fill(
        path,
        {
            2: good,
            3: {**good, "Deadband": None, "Consequence": None},
            4: {"Keep or Remove": "Remove"},
        },
    )
    decisions, matrix = read_madb(path)
    assert matrix[("Major", "3 to 10 min")] == "Medium"
    assert decisions[0].get("Rationalized Priority") == "Medium"
    p = progress(decisions)
    assert (p["kept"], p["removed"]) == (2, 1)
    probs = check_madb(decisions)
    assert any("row 3" in x and "Consequence is blank" in x for x in probs)
    assert any("row 4" in x and "no reason" in x for x in probs)
    assert not any("row 2" in x for x in probs)


def test_madb_drives_the_generator(pair, tmp_path):  # noqa: F811
    """A completed MADB, read back, generates the same rationalized plant
    as the site model it was written from."""
    from datetime import datetime

    from almetrics.episodes import parse_journal
    from almetrics.generator import ALL_FIXES, generate
    from almetrics.journal import load_events
    from almetrics.madb import (
        check_madb,
        fill_from_site,
        progress,
        read_madb,
        site_from_madb,
    )
    from almetrics.metrics import console_metrics

    before, _, _ = pair
    site = redmesa.build()
    path = fill_from_site(export_madb(before, tmp_path / "m.xlsx", site), site)
    decisions, _ = read_madb(path)
    assert progress(decisions)["open"] == 0
    assert check_madb(decisions) == []
    m_site = site_from_madb(site, decisions)
    out = []
    for s in (site, m_site):
        db = tmp_path / f"g{len(out)}.db"
        generate(s, db, datetime(2026, 8, 1), 15, ALL_FIXES, seed=9)
        out.append(console_metrics(parse_journal(load_events(db))))
    assert out[0] == out[1]


def test_changes_and_patch(pair, tmp_path):  # noqa: F811
    import json

    from almetrics.changes import change_list, write_changes
    from almetrics.madb import fill_from_site, read_madb

    before, _, _ = pair
    site = redmesa.build()
    path = fill_from_site(export_madb(before, tmp_path / "m.xlsx", site), site)
    decisions, _ = read_madb(path)
    ch = change_list(site, decisions)
    assert sum(c.field == "remove" for c in ch) == 5
    paths = write_changes(site, decisions, tmp_path / "out")
    patch = json.loads(paths["patch"].read_text())
    alarms = [a for tags in patch.values() for t in tags for a in t["alarms"]]
    assert len(alarms) == 144
    assert {"timeOnDelaySeconds", "setpointA", "deadband"} <= set(alarms[0])
    bound = [a for a in alarms if "enabled" in a]
    assert len(bound) == 43
    assert bound[0]["enabled"]["bindType"] == "Expression"
    assert bound[0]["enabled"]["value"].startswith(
        "!({[default]RedMesa/States/"
    )
    states = json.loads(paths["states"].read_text())["RedMesa/States"]
    assert {t["name"] for t in states} == {
        "CRYO_BYPASS",
        "K500A_DOWN",
        "SLUG",
        "FOAM",
        "POWER_DIP",
    }


def test_first_ten_after_rationalization(pair):  # noqa: F811
    from statistics import median

    from almetrics.states import first_ten

    before, after, _ = pair
    trip = next(
        a.source
        for a in redmesa.build().alarms
        if a.displaypath == "EC-420 XA-4207 Trip"
    )
    b = [n for _, n in first_ten(before, trip, "C2")]
    a = [n for _, n in first_ten(after, trip, "C2")]
    if b and a:
        assert median(a) < 10 <= median(b)
