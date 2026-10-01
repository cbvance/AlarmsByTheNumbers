"""Before and after: the report that proves the work paid off."""

from __future__ import annotations

from pathlib import Path

from .episodes import ParsedJournal
from .metrics import Targets, console_metrics
from .nuisance import find_chattering, stale_by_day, stale_summary

ROWS = [
    # key, label, target text, test the after value must pass
    ("per_day", "Annunciated per day", None, None),
    ("per_10min", "Average per 10 min", "1 to 2", lambda v: v <= 2),
    ("max_10min", "Peak in 10 min", "10 or fewer", lambda v: v <= 10),
    (
        "pct_10min_over",
        "10-min periods over 10 (%)",
        "under 1",
        lambda v: v < 1,
    ),
    ("pct_time_in_flood", "Time in flood (%)", "under 1", lambda v: v < 1),
    ("top10_pct", "Top ten share (%)", "1 to 5", lambda v: v <= 5),
    ("high_pct", "High and Critical share (%)", "about 5", lambda v: v <= 6),
    ("chattering", "Chattering alarms", "0", lambda v: v == 0),
    ("max_stale", "Most stale alarms on a day", "under 5", lambda v: v < 5),
]


def _extra(pj: ParsedJournal, console: str | None) -> dict:
    eps = [
        e for e in pj.annunciated() if console is None or e.console == console
    ]
    st = stale_summary(stale_by_day(pj, console))
    return {
        "chattering": len(find_chattering(eps)),
        "max_stale": st["max_stale"],
    }


# listing: compare
def compare(
    before: ParsedJournal,
    after: ParsedJournal,
    console: str | None = None,
    targets: Targets = Targets(),
) -> list[dict]:
    b = console_metrics(before, console, targets=targets) | _extra(
        before, console
    )
    a = console_metrics(after, console, targets=targets) | _extra(
        after, console
    )
    b["high_pct"], a["high_pct"] = (
        b["priority_mix"]["High"],
        a["priority_mix"]["High"],
    )
    out = []
    for key, label, target, test in ROWS:
        bv, av = float(b[key]), float(a[key])
        change = (100.0 * (av - bv) / bv) if bv else 0.0
        out.append(
            {
                "metric": label,
                "before": bv,
                "after": av,
                "change_pct": change,
                "target": target or "",
                "met": None if test is None else bool(test(av)),
                "met_before": None if test is None else bool(test(bv)),
            }
        )
    return out


# end listing


# listing: field_report
def field_report(
    before: ParsedJournal, after: ParsedJournal, outdir, consoles=None
) -> Path:
    """A before-and-after report for people who will not run the tools:
    one Markdown page with the tables and the charts they refer to."""
    from pathlib import Path

    from . import charts
    from .metrics import by_month

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    consoles = consoles or before.consoles()
    lines = [
        "# Alarm system: before and after",
        "",
        f"Before: {before.start:%d %b %Y} to {before.end:%d %b %Y}"
        f" ({before.days:.0f} days). After: {after.start:%d %b %Y} to"
        f" {after.end:%d %b %Y} ({after.days:.0f} days).",
        "",
    ]
    for c in [None] + consoles:
        rows = compare(before, after, c)
        lines += [
            f"## {'All consoles' if c is None else 'Console ' + c}",
            "",
            "| Metric | Before | After | Target | Met |",
            "|---|---:|---:|---|---|",
        ]
        for r in rows:
            met = "" if r["met"] is None else ("yes" if r["met"] else "no")
            lines.append(
                f"| {r['metric']} | {r['before']:.1f} |"
                f" {r['after']:.1f} | {r['target']} | {met} |"
            )
        lines.append("")
        if c is None:
            charts.before_after(rows, outdir / "before_after.png")
    trend = {c: by_month(before, c) + by_month(after, c) for c in consoles}
    charts.monthly_trend(
        trend, outdir / "monthly.png", title="Month by month, before and after"
    )
    lines += [
        "![Before and after](before_after.png)",
        "",
        "![Month by month](monthly.png)",
        "",
    ]
    path = outdir / "report.md"
    path.write_text("\n".join(lines))
    return path


# end listing
