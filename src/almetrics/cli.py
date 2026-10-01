"""almetrics: measure an Ignition alarm journal before you fix it.

    almetrics generate  --out data/redmesa_before.db
    almetrics check     data/redmesa_before.db
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

    def line(r):
        return "  ".join(str(v).ljust(w) for v, w in zip(r, widths)).rstrip()

    return "\n".join(
        [line(header), line(["-" * w for w in widths])]
        + [line(r) for r in rows]
    )


def cmd_generate(args):
    from .generator import generate

    site = _site(args.site or "redmesa")
    fixes = tuple(f for f in args.fixes.split(",") if f) if args.fixes else ()
    if getattr(args, "madb", None):
        from .madb import read_madb, site_from_madb

        site = site_from_madb(site, read_madb(args.madb)[0])
        print(f"rationalization taken from {args.madb}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    s = generate(
        site,
        args.out,
        datetime.fromisoformat(args.start),
        args.days,
        fixes,
        args.seed,
    )
    print(
        f"wrote {s['rows']:,} alarm_events rows ({s['activations']:,} activations) "
        f"to {s['db']}"
    )
    print(
        f"fixes: {', '.join(s['fixes']) or 'none (as found)'}; upsets planted: "
        f"{len(s['upsets'])}; chatter windows: {s['chatter_windows']}"
    )


def cmd_parse(args):
    pj, _ = _load(args)
    ann = pj.annunciated()
    print(f"{args.journal}")
    print(
        f"  {pj.start:%Y-%m-%d %H:%M} to {pj.end:%Y-%m-%d %H:%M}"
        f" ({pj.days:.1f} days)"
    )
    print(
        f"  episodes {len(pj.episodes):,}  annunciated {len(ann):,}"
        f"  shelved {sum(e.shelved for e in pj.episodes):,}"
    )
    print(
        f"  orphans {pj.orphans}  toggles {len(pj.toggles)}"
        f"  system rows {len(pj.system)}"
    )


def cmd_metrics(args):
    from .metrics import all_consoles, by_month

    pj, _ = _load(args)
    if getattr(args, "by", None) == "month":
        for c in pj.consoles():
            print(f"\nConsole {c}")
            rows = [
                [
                    r["month"],
                    f"{r['annunciated']:,}",
                    f"{r['per_day']:.0f}",
                    f"{r['per_10min']:.2f}",
                    r["max_10min"],
                    f"{r['pct_time_in_flood']:.1f}",
                    f"{r['top10_pct']:.1f}",
                ]
                for r in by_month(pj, c)
            ]
            print(
                _table(
                    rows,
                    [
                        "Month",
                        "Alarms",
                        "Per day",
                        "Per 10m",
                        "Peak 10m",
                        "%Flood",
                        "Top10%",
                    ],
                )
            )
        return
    ms = all_consoles(pj)
    if args.json:
        Path(args.json).write_text(
            json.dumps(ms, indent=2, default=str), encoding="utf-8"
        )
    rows = []
    for m in ms:
        mix = m["priority_mix"]
        rows.append(
            [
                m["console"],
                f"{m['annunciated']:,}",
                f"{m['per_day']:.0f}",
                f"{m['per_10min']:.2f}",
                m["max_10min"],
                f"{m['pct_10min_over']:.1f}",
                f"{m['pct_time_in_flood']:.1f}",
                f"{m['top10_pct']:.1f}",
                f"{mix['Low']:.0f}/{mix['Medium']:.0f}/{mix['High']:.0f}",
            ]
        )
    print(
        _table(
            rows,
            [
                "Console",
                "Alarms",
                "Per day",
                "Per 10m",
                "Peak 10m",
                "%10m>10",
                "%Flood",
                "Top10%",
                "L/M/H %",
            ],
        )
    )


def cmd_floods(args):
    from collections import Counter

    from .floods import classify, flood_summary, floods_for, recurring

    pj, _ = _load(args)
    for c in pj.consoles():
        fl = floods_for(pj, c)
        kinds = Counter(classify(f) for f in fl)
        mix = ", ".join(f"{n} {k}" for k, n in kinds.most_common())
        print(f"\nConsole {c}: {len(fl)} floods")
        print(f"  {mix}")
        big = sorted(fl, key=lambda f: -f.count)[: args.top]
        rows = [
            [
                s["kind"],
                f"{s['start']:%Y-%m-%d %H:%M}",
                s["minutes"],
                s["alarms"],
                s["peak_10min"],
                s["first_out"][:40],
            ]
            for s in map(flood_summary, big)
        ]
        print(
            _table(
                rows,
                [
                    "Kind",
                    "Start",
                    "Minutes",
                    "Alarms",
                    "Peak 10m",
                    "First out",
                ],
            )
        )
        print("Recurring first-out alarms:")
        for name, n in recurring(fl)[:5]:
            print(f"  {n:4d}  {name}")


def cmd_chatter(args):
    from .nuisance import chatterers, find_chattering, find_fleeting

    pj, _ = _load(args)
    eps = pj.annunciated()
    ch = find_chattering(eps, args.count, args.window)
    rows = [
        [
            s.console,
            s.displaypath[:44],
            s.activations,
            s.bursts,
            s.in_bursts,
            s.max_in_window,
        ]
        for s in sorted(ch.values(), key=lambda s: -s.activations)
    ]
    print(f"Chattering: {args.count}+ activations within {args.window:.0f} s")
    print(
        _table(
            rows,
            [
                "Con",
                "Alarm",
                "Activations",
                "Bursts",
                "In bursts",
                "Max/window",
            ],
        )
    )
    fl = find_fleeting(eps, args.fleeting, chatterers(ch))
    names = {e.source: e.displaypath for e in eps}
    print(
        f"\nFleeting: cleared within {args.fleeting:.0f} s (mostly-chattering alarms excluded)"
    )
    for src, n in sorted(fl.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {n:6d}  {names[src]}")


def cmd_stale(args):
    from .nuisance import stale_by_day, stale_summary

    pj, _ = _load(args)
    for c in pj.consoles():
        s = stale_summary(stale_by_day(pj, c, args.hours))
        print(
            f"\nConsole {c}: most stale on a day {s['max_stale']},"
            f" mean {s['mean_stale']:.1f}"
        )
        print(
            f"  days with 5 or more {s['days_over_5']} of {s['days']},"
            f" mean standing {s['mean_standing']:.1f}"
        )
        for name, age in s["longest"][:10]:
            print(f"  {age:6.1f} days  {name}")
    print(f"\nNote: alarms active before {pj.start:%Y-%m-%d} are invisible;")
    print(f"the first {args.hours:.0f} h undercount.")


def cmd_badactors(args):
    from .badactors import bad_actors

    pj, _ = _load(args)
    acts = bad_actors(pj, args.top, args.console)
    rows = [
        [
            a.rank,
            a.console,
            a.displaypath[:25],
            {"Medium": "Med", "Critical": "Crit"}.get(a.priority, a.priority),
            f"{a.count:,}",
            f"{a.pct:.1f}",
            a.diagnosis,
        ]
        for a in acts
    ]
    print(
        _table(
            rows,
            [
                "#",
                "Con",
                "Alarm",
                "Pri",
                "Count",
                "%",
                "First guess",
            ],
        )
    )
    if args.chart:
        from .charts import pareto

        print(f"chart: {pareto(acts, args.chart)}")
    if args.cards:
        from .charts import actor_card

        for a in acts:
            p = actor_card(pj, a, Path(args.cards) / f"actor_{a.rank:02d}.png")
            print(f"card: {p}")
    if args.what_if:
        from .badactors import what_if

        print("\nIf the top alarms were fixed:")
        print(
            _table(
                [
                    [
                        r["removed"],
                        f"{r['per_day']:.0f}",
                        r["max_10min"],
                        f"{r['pct_time_in_flood']:.1f}",
                    ]
                    for r in what_if(pj, args.top, args.console)
                ],
                ["Fixed", "Per day", "Peak 10m", "%Flood"],
            )
        )


def cmd_shelving(args):
    import textwrap
    from statistics import median

    from .shelving import long_disabled, shelve_periods, shelving_report

    pj, _ = _load(args)
    rep = shelving_report(pj)
    for w in rep.warnings:
        print(textwrap.fill(f"WARNING: {w}", 79, subsequent_indent="  "))
    print(f"Shelved activations: {rep.shelved_activations:,}")
    for name, n, share in rep.shelved_by_alarm[:10]:
        print(f"  {n:6,}  {100 * share:5.1f}% of its activations  {name}")
    periods = shelve_periods(pj)
    if periods:
        mins = [p.minutes for p in periods]
        print(
            f"Shelve periods seen: {len(periods)}, median span "
            f"{median(mins):.0f} min, longest {max(mins):.0f} min"
        )
    print(
        f"Disabled spans: {len(rep.disabled_spans)};"
        f" look state-based: {rep.state_events};"
        f" still disabled: {len(rep.still_disabled)}"
    )
    for s in long_disabled(rep, pj.end)[:10]:
        print(f"  {s.hours(pj.end):7.1f} h disabled  {s.displaypath}")


def cmd_check(args):
    from .check import check_journal

    rep = check_journal(load_events(args.journal))
    for line in rep.findings:
        print(f"- {line}")


def cmd_madb_check(args):
    from .madb import check_madb, progress, read_madb

    decisions, _ = read_madb(args.workbook)
    p = progress(decisions)
    print(
        f"{args.workbook}: {p['alarms']} alarms, {p['kept']} kept,"
        f" {p['removed']} removed, {p['open']} not yet rationalized"
    )
    problems = check_madb(decisions)
    print(f"{len(problems)} problem(s)")
    for line in problems:
        print(f"  {line}")
    return 1 if problems else 0


def cmd_changes(args):
    from collections import Counter

    from .changes import change_list, write_changes
    from .madb import read_madb

    site = _site(args.site or "redmesa")
    decisions, _ = read_madb(args.workbook)
    paths = write_changes(site, decisions, args.out)
    kinds = Counter(c.field for c in change_list(site, decisions))
    print(
        f"{sum(kinds.values())} changes on"
        f" {len({(c.tag, c.alarm) for c in change_list(site, decisions)})}"
        " alarms"
    )
    for k, n in kinds.most_common():
        print(f"  {n:4d}  {k}")
    for p in paths.values():
        print(f"wrote {p}")


def cmd_delays(args):
    from .delays import delay_table

    pj, _ = _load(args)
    eps = [e for e in pj.annunciated() if e.displaypath == args.alarm]
    if not eps:
        print(f"no annunciated episodes for {args.alarm!r}")
        return 1
    on, off = (0, 5, 10, 15, 30, 60), (0, 10, 30, 60)
    rows = [
        [f"{a} s"] + [f"{n:,}" for n in r]
        for a, r in zip(on, delay_table(eps, pj.end, on, off))
    ]
    print(f"{args.alarm}: activations by on-delay (rows), off-delay")
    print(_table(rows, ["On \\ Off"] + [f"{b} s" for b in off]))


def cmd_madb(args):
    from .madb import export_madb

    pj, site = _load(args)
    path = export_madb(pj, args.out, site, str(args.journal))
    if args.decided:
        from .madb import fill_from_site

        fill_from_site(path, site)
        print("filled with the site model's rationalization decisions")
    print(f"wrote {path}")


def cmd_compare(args):
    from .compare import compare

    site = _site(args.site)
    cmap = (
        ConsoleMap.from_csv(args.consoles)
        if args.consoles
        else (ConsoleMap(site.consoles) if site else ConsoleMap())
    )
    b = parse_journal(load_events(args.before), cmap)
    a = parse_journal(load_events(args.after), cmap)
    for c in [None] + b.consoles():
        rows = compare(b, a, c)
        print(f"\n{'All consoles' if c is None else 'Console ' + c}")
        print(
            _table(
                [
                    [
                        r["metric"],
                        f"{r['before']:.1f}",
                        f"{r['after']:.1f}",
                        f"{r['change_pct']:+.0f}%",
                        r["target"],
                    ]
                    for r in rows
                ],
                ["Metric", "Before", "After", "Change", "Target"],
            )
        )
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
    made.append(
        charts.ten_minute_histogram(
            ten_minute_counts(
                [e.active for e in pj.annunciated()], pj.start, pj.end
            ),
            out / "ten_minute_histogram.png",
        )
    )
    made.append(charts.pareto(bad_actors(pj), out / "pareto.png"))
    made.append(
        charts.priority_mix(
            console_metrics(pj)["priority_mix"], out / "priority_mix.png"
        )
    )
    made.append(charts.load_by_group(pj, out / "load_by_area.png"))
    made.append(charts.duration_histogram(pj, out / "durations.png"))
    made.append(charts.ack_histogram(pj, out / "time_to_ack.png"))
    from .floods import floods_for

    fl = [f for c in pj.consoles() for f in floods_for(pj, c)]
    made.append(charts.flood_sizes(fl, out / "flood_sizes.png"))
    made.append(charts.first_outs(fl, out / "first_outs.png"))
    made.append(charts.chatter_profile(pj, out / "chatter_profile.png"))
    made.append(charts.stale_timeline(pj, out / "stale_timeline.png"))
    made.append(charts.stale_gantt(pj, out / "stale_gantt.png"))
    if any(e.shelved for e in pj.episodes):
        made.append(charts.shelving_chart(pj, out / "shelving.png"))
    raw = load_events(args.journal)
    made.append(
        charts.rows_per_day(
            raw,
            out / "rows_per_day.png",
            [
                e.eventtime
                for e in raw
                if e.is_system and "Startup" in e.source
            ],
        )
    )
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
        (
            "generate before",
            cmd_generate,
            NS(
                site="redmesa",
                out=before,
                start="2026-01-01",
                days=181,
                fixes="",
                seed=args.seed,
            ),
        ),
        (
            "generate after",
            cmd_generate,
            NS(
                site="redmesa",
                out=after,
                start="2026-08-01",
                days=91,
                fixes="all",
                seed=args.seed,
            ),
        ),
    ]
    j = dict(journal=before, site="redmesa", consoles=None)
    reports = [
        ("check", cmd_check, NS(**j)),
        ("parse", cmd_parse, NS(**j)),
        ("metrics", cmd_metrics, NS(**j, json=out / "metrics.json")),
        ("floods", cmd_floods, NS(**j, top=10)),
        ("chatter", cmd_chatter, NS(**j, count=3, window=60.0, fleeting=5.0)),
        ("stale", cmd_stale, NS(**j, hours=24.0)),
        (
            "badactors",
            cmd_badactors,
            NS(
                **j,
                top=10,
                console=None,
                chart=out / "pareto.png",
                cards=out / "cards",
                what_if=True,
            ),
        ),
        ("shelving", cmd_shelving, NS(**j)),
        ("madb", cmd_madb, NS(**j, out=out / "madb.xlsx", decided=False)),
        ("charts", cmd_charts, NS(**j, outdir=out / "charts")),
        (
            "compare",
            cmd_compare,
            NS(
                before=before,
                after=after,
                site="redmesa",
                consoles=None,
                chart=out / "before_after.png",
            ),
        ),
    ]
    for name, fn, ns in steps:
        print(f"[build] {name}")
        fn(ns)
    for name, fn, ns in reports:
        print(f"[build] {name} -> out/{name}.txt")
        with (
            open(out / f"{name}.txt", "w", encoding="utf-8") as f,
            contextlib.redirect_stdout(f),
        ):
            fn(ns)
    print(f"[build] done: {data} and {out}")


# end listing


def cmd_stages(args):
    from .stages import run_stages

    site = _site(args.site or "redmesa")
    rows = run_stages(
        site, datetime.fromisoformat(args.start), args.days, args.seed
    )
    print(
        _table(
            [
                [
                    r["stage"],
                    f"{r['per_day']:.0f}",
                    r["peak_10min"],
                    f"{r['time_in_flood']:.1f}",
                    f"{r['high_pct']:.1f}",
                    r["chattering"],
                ]
                for r in rows
            ],
            ["Stage", "Per day", "Peak 10m", "%Flood", "High %", "Chatter"],
        )
    )
    if args.chart:
        from .charts import stages_chart

        print(f"chart: {stages_chart(rows, args.chart)}")


def cmd_export(args):
    for p in export_csv(args.journal, args.outdir):
        print(p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="almetrics", description=__doc__.split("\n")[0]
    )
    ap.add_argument(
        "--version", action="version", version=f"almetrics {__version__}"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    def journal_cmd(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument(
            "journal", type=Path, help="SQLite journal or alarm_events CSV"
        )
        p.add_argument("--site", help="built-in site model (redmesa)")
        p.add_argument("--consoles", type=Path, help="CSV of prefix,console")
        p.set_defaults(fn=fn)
        return p

    g = sub.add_parser("generate", help="write a synthetic Red Mesa journal")
    g.add_argument("--out", default="data/redmesa_before.db")
    g.add_argument("--start", default="2026-01-01")
    g.add_argument("--days", type=int, default=181)
    g.add_argument(
        "--fixes",
        default="",
        help="comma list: " + "deadband,priority,remove,state,stale or all",
    )
    g.add_argument("--seed", type=int, default=1843)
    g.add_argument("--site", default="redmesa")
    g.add_argument(
        "--madb",
        type=Path,
        help="take rationalized settings from a filled MADB",
    )
    g.set_defaults(fn=cmd_generate)

    journal_cmd(
        "check", cmd_check, "check coverage and quality before measuring"
    )
    journal_cmd("parse", cmd_parse, "rebuild episodes and report counts")
    p = journal_cmd("metrics", cmd_metrics, "headline metrics per console")
    p.add_argument("--by", choices=["month"], help="break out by month")
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
    p.add_argument("--cards", type=Path, help="folder for one card per alarm")
    p.add_argument(
        "--what-if",
        action="store_true",
        help="metrics as the top alarms are removed",
    )
    journal_cmd("shelving", cmd_shelving, "shelving and suppression analysis")
    p = journal_cmd("madb", cmd_madb, "export the MADB workbook")
    p.add_argument("--out", type=Path, default=Path("out/madb.xlsx"))
    p.add_argument(
        "--decided",
        action="store_true",
        help="fill in the site model's decisions (Red Mesa)",
    )
    p = journal_cmd("charts", cmd_charts, "standard chart set")
    p.add_argument("--outdir", type=Path, default=Path("out/charts"))
    b = sub.add_parser("build", help="generate both journals and every report")
    b.add_argument("--root", default=".", help="repo folder to build into")
    b.add_argument("--seed", type=int, default=1843)
    b.set_defaults(fn=cmd_build)
    ch = sub.add_parser("changes", help="configuration changes from a MADB")
    ch.add_argument("workbook", type=Path)
    ch.add_argument("--site", default="redmesa")
    ch.add_argument("--out", type=Path, default=Path("out/changes"))
    ch.set_defaults(fn=cmd_changes)
    p = journal_cmd("delays", cmd_delays, "replay on- and off-delays")
    p.add_argument("--alarm", required=True, help="display path")
    mc = sub.add_parser("madb-check", help="check a filled MADB workbook")
    mc.add_argument("workbook", type=Path)
    mc.set_defaults(fn=cmd_madb_check)
    st = sub.add_parser("stages", help="apply fixes one kind at a time")
    st.add_argument("--site", default="redmesa")
    st.add_argument("--start", default="2026-01-01")
    st.add_argument("--days", type=int, default=181)
    st.add_argument("--seed", type=int, default=1843)
    st.add_argument("--chart", type=Path)
    st.set_defaults(fn=cmd_stages)
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
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
