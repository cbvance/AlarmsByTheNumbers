from openpyxl import load_workbook

from almetrics.badactors import bad_actors
from almetrics.compare import compare
from almetrics.madb import export_madb
from almetrics.shelving import shelving_report
from almetrics.sites import redmesa
from test_generator import pair  # noqa: F401  (module fixture)


def test_bad_actors_ranked(pair):  # noqa: F811
    before, _, _ = pair
    acts = bad_actors(before)
    assert len(acts) == 10
    assert [a.count for a in acts] == sorted(
        (a.count for a in acts), reverse=True
    )
    assert acts[0].diagnosis.startswith("chattering")
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
