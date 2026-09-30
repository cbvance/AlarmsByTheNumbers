"""almetrics: measure an Ignition alarm journal before you fix it.

    almetrics generate  --out data/redmesa_before.db
    almetrics metrics   data/redmesa_before.db --site redmesa
    almetrics floods    data/redmesa_before.db --site redmesa
    almetrics chatter   data/redmesa_before.db --site redmesa
    almetrics stale     data/redmesa_before.db --site redmesa
    almetrics badactors data/redmesa_before.db --site redmesa
    almetrics shelving  data/redmesa_before.db --site redmesa
    almetrics madb      data/redmesa_before.db --site redmesa --out out/madb.xlsx
    almetrics compare   data/redmesa_before.db data/redmesa_after.db --site redmesa
    almetrics charts    data/redmesa_before.db --site redmesa --outdir out/charts
    almetrics build     (everything above, into data/ and out/)

Use --consoles map.csv (columns prefix,console) instead of --site on a
real plant journal. With neither, everything reports as console ALL.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .episodes import parse_journal
from .journal import export_csv, load_events
from .site import PRIORITY_NAMES, ConsoleMap


def _site(name: str | None):
    if not name:
        return None
    if name.lower() == "redmesa":
        from .sites import redmesa
        return redmesa.build()
    raise SystemExit(f"unknown site {name!r} (built in: redmesa)")


def _load(args):
    site = _site(getattr(args, "site", None))
    if getattr(args, "consoles", None):
        cmap = ConsoleMap.from_csv(args.consoles)
    elif site:
        cmap = ConsoleMap(site.consoles)
    else:
        cmap = ConsoleMap()
    return parse_journal(load_events(args.journal), cmap), site


def _table(rows: list[list], header: list[str]) -> str:
    cols = list(zip(header, *rows)) if rows else [(h,) for h in header]
    widths = [max(len(str(v)) for v in col) for col in cols]
    line = lambda r: "  ".join(str(v).ljust(w) for v, w in zip(r, widths))
    return "\n".join([line(header), line(["-" * w for w in widths])] + [line(r) for r in rows])


def cmd_generate(args):
    from .generator import generate
    site = _site(args.site or "redmesa")
    fixes = tuple(f for f in args.fixes.split(",") if f) if args.fixes else ()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    s = generate(site, args.out, datetime.fromisoformat(args.start), args.days, fixes, args.seed)
    print(f"wrote {s['rows']:,} alarm_events rows ({s['activations']:,} activations) "
          f"to {s['db']}")
    print(f"fixes: {', '.join(s['fixes']) or 'none (as found)'}; upsets planted: "
          f"{len(s['upsets'])}; chatter windows: {s['chatter_windows']}")


def cmd_parse(args):
    pj, _ = _load(args)
    ann = pj.annunciated()
    print(f"{args.journal}: {pj.start:%Y-%m-%d %H:%M} to {pj.end:%Y-%m-%d %H:%M} "
          f"({pj.days:.1f} days)")
    print(f"episodes {len(pj.episodes):,}  annunciated {len(ann):,}  "
          f"shelved {sum(e.shelved for e in pj.episodes):,}  orphans {pj.orphans}  "
          f"toggles {len(pj.toggles)}  system rows {len(pj.system)}")


def cmd_metrics(args):
    from .metrics import all_consoles
    pj, _ = _load(args)
    ms = all_consoles(pj)
    if args.json:
        Path(args.json).write_text(json.dumps(ms, indent=2, default=str), encoding="utf-8")
    rows = []
    for m in ms:
        mix = m["priority_mix"]
        rows.append([m["console"], f"{m['annunciated']:,}", f"{m['per_day']:.0f}",
                     f"{m['per_10min']:.2f}", m["max_10min"], f"{m['pct_10min_over']:.1f}",
                     f"{m['pct_time_in_flood']:.1f}", f"{m['top10_pct']:.1f}",
                     f"{mix['Low']:.0f}/{mix['Medium']:.0f}/{mix['High']:.0f}"])
    print(_table(rows, ["Console", "Alarms", "Per day", "Per 10m", "Peak 10m",
                        "%10m>10", "%Flood", "Top10%", "L/M/H %"]))


def cmd_floods(args):
    from .floods import flood_summary, floods_for, recurring
    pj, _ = _load(args)
    for c in pj.consoles():
        fl = floods_for(pj, c)
        print(f"\nConsole {c}: {len(fl)} floods")
        big = sorted(fl, key=lambda f: -f.count)[: args.top]
        rows = [[f"{s['start']:%Y-%m-%d %H:%M}", s["minutes"], s["alarms"], s["peak_10min"],
                 s["first_out"][:40]] for s in map(flood_summary, big)]
        print(_table(rows, ["Start", "Minutes", "Alarms", "Peak 10m", "First out"]))
        print("Recurring first-out alarms:")
        for name, n in recurring(fl)[:5]:
            print(f"  {n:4d}  {name}")


def cmd_chatter(args):
    from .nuisance import chatterers, find_chattering, find_fleeting
    pj, _ = _load(args)
    eps = pj.annunciated()
    ch = find_chattering(eps, args.count, args.window)
    rows = [[s.console, s.displaypath[:44], s.activations, s.bursts, s.in_bursts, s.max_in_window]
            for s in sorted(ch.values(), key=lambda s: -s.activations)]
    print(f"Chattering: {args.count}+ activations within {args.window:.0f} s")
    print(_table(rows, ["Con", "Alarm", "Activations", "Bursts", "In bursts", "Max/window"]))
    fl = find_fleeting(eps, args.fleeting, chatterers(ch))
    names = {e.source: e.displaypath for e in eps}
    print(f"\nFleeting: cleared within {args.fleeting:.0f} s (mostly-chattering alarms excluded)")
    for src, n in sorted(fl.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {n:6d}  {names[src]}")


def cmd_stale(args):
    from .nuisance import stale_by_day, stale_summary
    pj, _ = _load(args)
    for c in pj.consoles():
        s = stale_summary(stale_by_day(pj, c, args.hours))
        print(f"\nConsole {c}: most stale on a day {s['max_stale']}, mean {s['mean_stale']:.1f}, "
              f"days with 5 or more {s['days_over_5']} of {s['days']}, "
              f"mean standing {s['mean_standing']:.1f}")
        for name, age in s["longest"][:10]:
            print(f"  {age:6.1f} days  {name}")
    print(f"\nNote: alarms already active before {pj.start:%Y-%m-%d} are invisible; "
          f"the first {args.hours:.0f} h undercount.")


def cmd_badactors(args):
    from .badactors import bad_actors
    pj, _ = _load(args)
    acts = bad_actors(pj, args.top, args.console)
    rows = [[a.rank, a.console, a.displaypath[:36], a.priority, f"{a.count:,}",
             f"{a.pct:.1f}", f"{a.cum_pct:.1f}", a.diagnosis] for a in acts]
    print(_table(rows, ["#", "Con", "Alarm", "Priority", "Count", "%", "Cum %", "First guess"]))
    if args.chart:
        from .charts import pareto
        print(f"chart: {pareto(acts, args.chart)}")


def cmd_shelving(args):
    from .shelving import long_disabled, shelving_report
    pj, _ = _load(args)
    rep = shelving_report(pj)
    for w in rep.warnings:
        print(f"WARNING: {w}")
    print(f"Shelved activations: {rep.shelved_activations:,}")
    for name, n, share in rep.shelved_by_alarm[:10]:
        print(f"  {n:6d}  {100 * share:5.1f}% of its activations  {name}")
    print(f"Disabled spans: {len(rep.disabled_spans)}; look state-based: {rep.state_events}; "
          f"still disabled at end: {len(rep.still_disabled)}")
    for s in long_disabled(rep, pj.end)[:10]:
        print(f"  {s.hours(pj.end):7.1f} h disabled  {s.displaypath}")


def cmd_madb(args):
    from .madb import export_madb
    pj, site = _load(args)
    print(f"wrote {export_madb(pj, args.out, site, str(args.journal))}")


def cmd_compare(args):
    from .compare import compare
    site = _site(args.site)
    cmap = ConsoleMap.from_csv(args.consoles) if args.consoles else (
        ConsoleMap(site.consoles) if site else ConsoleMap())
    b = parse_journal(load_events(args.before), cmap)
    a = parse_journal(load_events(args.after), cmap)
    for c in [None] + b.consoles():
        rows = compare(b, a, c)
        print(f"\n{'All consoles' if c is None else 'Console ' + c}")
        print(_table([[r["metric"], f"{r['before']:.1f}", f"{r['after']:.1f}",
                       f"{r['change_pct']:+.0f}%", r["target"]] for r in rows],
                     ["Metric", "Before", "After", "Change", "Target"]))
        if args.chart and c is None:
            from .charts import before_after
            print(f"chart: {before_after(rows, args.chart)}")


def cmd_charts(args):
    from . import charts
    from .badactors import bad_actors
    from .metrics import console_metrics, ten_minute_counts
    pj, _ = _load(args)
    out = Path(args.outdir)
    made = [charts.daily_rate(pj, out / "daily_rate.png")]
    made.append(charts.ten_minute_histogram(
        ten_minute_counts([e.active for e in pj.annunciated()], pj.start, pj.end),
        out / "ten_minute_histogram.png"))
    made.append(charts.pareto(bad_actors(pj), out / "pareto.png"))
    made.append(charts.priority_mix(console_metrics(pj)["priority_mix"], out / "priority_mix.png"))
    made.append(charts.load_by_group(pj, out / "load_by_area.png"))
    pj_site = _site(getattr(args, "site", None))
    if pj_site:
        made.append(charts.inventory(pj_site, out / "inventory.png"))
    for p in made:
        print(p)


# listing: cmd_build
def cmd_build(args):
    """Generate both Red Mesa journals and every report the book uses."""
    import contextlib
    from types import SimpleNamespace as NS
    root = Path(args.root)
    data, out = root / "data", root / "out"
    out.mkdir(parents=True, exist_ok=True)
    before, after = data / "redmesa_before.db", data / "redmesa_after.db"
    steps = [
        ("generate before", cmd_generate, NS(site="redmesa", out=before, start="2026-01-01",
                                             days=181, fixes="", seed=args.seed)),
        ("generate after", cmd_generate, NS(site="redmesa", out=after, start="2026-08-01",
                                            days=91, fixes="all", seed=args.seed)),
    ]
    j = dict(journal=before, site="redmesa", consoles=None)
    reports = [
        ("parse", cmd_parse, NS(**j)),
        ("metrics", cmd_metrics, NS(**j, json=out / "metrics.json")),
        ("floods", cmd_floods, NS(**j, top=10)),
        ("chatter", cmd_chatter, NS(**j, count=3, window=60.0, fleeting=5.0)),
        ("stale", cmd_stale, NS(**j, hours=24.0)),
        ("badactors", cmd_badactors, NS(**j, top=10, console=None, chart=out / "pareto.png")),
        ("shelving", cmd_shelving, NS(**j)),
        ("madb", cmd_madb, NS(**j, out=out / "madb.xlsx")),
        ("charts", cmd_charts, NS(**j, outdir=out / "charts")),
        ("compare", cmd_compare, NS(before=before, after=after, site="redmesa", consoles=None,
                                    chart=out / "before_after.png")),
    ]
    for name, fn, ns in steps:
        print(f"[build] {name}")
        fn(ns)
    for name, fn, ns in reports:
        print(f"[build] {name} -> out/{name}.txt")
        with open(out / f"{name}.txt", "w", encoding="utf-8") as f, contextlib.redirect_stdout(f):
            fn(ns)
    print(f"[build] done: {data} and {out}")
# end listing


def cmd_export(args):
    for p in export_csv(args.journal, args.outdir):
        print(p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="almetrics", description=__doc__.split("\n")[0])
    ap.add_argument("--version", action="version", version=f"almetrics {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def journal_cmd(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("journal", type=Path, help="SQLite journal or alarm_events CSV")
        p.add_argument("--site", help="built-in site model (redmesa)")
        p.add_argument("--consoles", type=Path, help="CSV of prefix,console")
        p.set_defaults(fn=fn)
        return p

    g = sub.add_parser("generate", help="write a synthetic Red Mesa journal")
    g.add_argument("--out", default="data/redmesa_before.db")
    g.add_argument("--start", default="2026-01-01")
    g.add_argument("--days", type=int, default=181)
    g.add_argument("--fixes", default="", help="comma list: " + "deadband,priority,remove,state,stale or all")
    g.add_argument("--seed", type=int, default=1843)
    g.add_argument("--site", default="redmesa")
    g.set_defaults(fn=cmd_generate)

    journal_cmd("parse", cmd_parse, "rebuild episodes and report counts")
    p = journal_cmd("metrics", cmd_metrics, "headline metrics per console")
    p.add_argument("--json", type=Path)
    p = journal_cmd("floods", cmd_floods, "flood episodes per console")
    p.add_argument("--top", type=int, default=10)
    p = journal_cmd("chatter", cmd_chatter, "chattering and fleeting alarms")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--window", type=float, default=60.0)
    p.add_argument("--fleeting", type=float, default=5.0)
    p = journal_cmd("stale", cmd_stale, "stale and standing alarms")
    p.add_argument("--hours", type=float, default=24.0)
    p = journal_cmd("badactors", cmd_badactors, "top-N bad actor report")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--console")
    p.add_argument("--chart", type=Path)
    journal_cmd("shelving", cmd_shelving, "shelving and suppression analysis")
    p = journal_cmd("madb", cmd_madb, "export the MADB workbook")
    p.add_argument("--out", type=Path, default=Path("out/madb.xlsx"))
    p = journal_cmd("charts", cmd_charts, "standard chart set")
    p.add_argument("--outdir", type=Path, default=Path("out/charts"))
    b = sub.add_parser("build", help="generate both journals and every report")
    b.add_argument("--root", default=".", help="repo folder to build into")
    b.add_argument("--seed", type=int, default=1843)
    b.set_defaults(fn=cmd_build)
    p = sub.add_parser("export-csv", help="dump both journal tables to CSV")
    p.add_argument("journal", type=Path)
    p.add_argument("outdir", type=Path)
    p.set_defaults(fn=cmd_export)
    c = sub.add_parser("compare", help="before and after report")
    c.add_argument("before", type=Path)
    c.add_argument("after", type=Path)
    c.add_argument("--site")
    c.add_argument("--consoles", type=Path)
    c.add_argument("--chart", type=Path)
    c.set_defaults(fn=cmd_compare)

    args = ap.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
