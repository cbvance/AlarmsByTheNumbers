"""Grayscale charts sized for a 4.25 in square figure at 300 dpi.

Every figure in the book that shows data is drawn by these functions, so
anyone who runs the repo gets the same pictures from the same numbers.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from .episodes import ParsedJournal  # noqa: E402
from .metrics import daily_counts  # noqa: E402

SIZE = (4.25, 4.25)
DPI = 300
INK = ["#000000", "#7f7f7f", "#bfbfbf", "#404040"]
DASH = ["-", "--", ":", "-."]


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.edgecolor": "#000000",
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.0,
            "savefig.facecolor": "white",
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _save(fig, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


# listing: chart_daily_rate
def daily_rate(
    pj: ParsedJournal,
    path,
    consoles: list[str] | None = None,
    title: str = "Annunciated alarms per console per day",
) -> Path:
    """One panel per console: daily bars against 1 and 2 per 10 min."""
    style()
    consoles = consoles or pj.consoles()
    days = int(round(pj.days))
    day0 = datetime(pj.start.year, pj.start.month, pj.start.day)
    x = [day0 + timedelta(days=i) for i in range(days)]
    series = {
        c: daily_counts(
            [e.active for e in pj.annunciated() if e.console == c],
            pj.start,
            days,
        )
        for c in consoles
    }
    top = max(max(y) for y in series.values()) * 1.1
    fig, axes = plt.subplots(
        len(consoles), 1, figsize=SIZE, sharex=True, squeeze=False
    )
    for ax, c in zip(axes[:, 0], consoles):
        ax.bar(x, series[c], width=1.0, color="#7f7f7f", edgecolor="none")
        for level, text in ((144, "1 per 10 min"), (288, "2 per 10 min")):
            ax.axhline(level, color="#000000", lw=0.7, ls="--")
            ax.text(
                x[0],
                level,
                f" {text} ({level}/day)",
                ha="left",
                va="bottom",
                fontsize=6.5,
                bbox=dict(fc="white", ec="none", pad=0.5),
            )
        ax.set_ylim(0, top)
        ax.set_ylabel(f"Console {c}\nalarms per day")
    axes[0, 0].set_title(title)
    axes[-1, 0].xaxis.set_major_locator(mdates.MonthLocator())
    axes[-1, 0].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    return _save(fig, path)


# end listing


# listing: chart_flood_minutes
def flood_minutes(
    pj: ParsedJournal,
    t0: datetime,
    minutes: int,
    path,
    consoles: list[str] | None = None,
    begin: int = 10,
    title: str = "Alarm arrivals during an upset",
) -> Path:
    """Top: arrivals per minute by console. Bottom: rolling 10-min count."""
    style()
    consoles = consoles or pj.consoles()
    fig, (top, bot) = plt.subplots(
        2, 1, figsize=SIZE, sharex=True, gridspec_kw={"height_ratios": [1, 1]}
    )
    xs = list(range(minutes))
    base = [0] * minutes
    totals = [0] * minutes
    for i, c in enumerate(consoles):
        per = [0] * minutes
        for e in pj.annunciated():
            if e.console == c and t0 <= e.active < t0 + timedelta(
                minutes=minutes
            ):
                per[int((e.active - t0).total_seconds() // 60)] += 1
        top.bar(
            xs,
            per,
            bottom=base,
            width=0.9,
            color=INK[i % 3],
            edgecolor="#000000",
            lw=0.3,
            label=f"Console {c}",
        )
        base = [b + p for b, p in zip(base, per)]
        totals = [t + p for t, p in zip(totals, per)]
    top.set_ylabel("Alarms per minute")
    top.legend(loc="upper right", frameon=False)
    top.set_title(title)
    rolling = [sum(totals[max(0, i - 9) : i + 1]) for i in xs]
    bot.plot(xs, rolling, color="#000000", lw=1.0)
    bot.axhline(begin, color="#000000", lw=0.6, ls="--")
    bot.text(
        minutes - 1,
        begin,
        f"flood threshold ({begin})",
        ha="right",
        va="bottom",
        fontsize=6.5,
    )
    bot.set_ylabel("Alarms in last 10 min")
    bot.set_xlabel(f"Minutes after {t0:%H:%M} on {t0:%d %b %Y}")
    return _save(fig, path)


# end listing


def ten_minute_histogram(
    counts: list[int], path, title="Alarms per 10-minute period"
) -> Path:
    style()
    fig, ax = plt.subplots(figsize=SIZE)
    edges = [0, 1, 2, 3, 5, 10, 20, 50, 100, 1000]
    labels = ["0", "1", "2", "3-4", "5-9", "10-19", "20-49", "50-99", "100+"]
    bins = [0] * (len(edges) - 1)
    for c in counts:
        for i in range(len(edges) - 1):
            if edges[i] <= c < edges[i + 1]:
                bins[i] += 1
                break
    total = sum(bins) or 1
    pct = [100 * b / total for b in bins]
    ax.bar(
        labels,
        pct,
        color=["#bfbfbf"] * 5 + ["#000000"] * 4,
        edgecolor="#000000",
        lw=0.4,
    )
    ax.set_ylabel("Percent of 10-minute periods")
    ax.set_xlabel("Alarms in the period")
    ax.set_title(title)
    return _save(fig, path)


def pareto(actors, path, title="Top ten alarms by count") -> Path:
    style()
    fig, ax = plt.subplots(figsize=SIZE)
    names = [f"{a.rank}" for a in actors]
    ax.bar(
        names,
        [a.pct for a in actors],
        color="#7f7f7f",
        edgecolor="#000000",
        lw=0.4,
    )
    ax2 = ax.twinx()
    ax2.plot(
        names, [a.cum_pct for a in actors], color="#000000", marker="o", ms=3
    )
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Cumulative percent")
    ax2.spines["right"].set_visible(True)
    ax.set_ylabel("Percent of all annunciated alarms")
    ax.set_xlabel("Rank (see table)")
    ax.set_title(title)
    return _save(fig, path)


def priority_mix(
    mix: dict[str, float],
    path,
    target=(80, 15, 5),
    title="Annunciated priority mix",
) -> Path:
    style()
    fig, ax = plt.subplots(figsize=SIZE)
    cats = ["Low", "Medium", "High"]
    xs = range(3)
    ax.bar(
        [x - 0.2 for x in xs],
        [mix.get(c, 0) for c in cats],
        0.4,
        color="#000000",
        label="Measured",
    )
    ax.bar(
        [x + 0.2 for x in xs],
        target,
        0.4,
        color="white",
        edgecolor="#000000",
        hatch="////",
        label="Target",
    )
    ax.set_xticks(list(xs), cats)
    ax.set_ylabel("Percent of annunciated alarms")
    ax.set_title(title)
    ax.legend(frameon=False)
    return _save(fig, path)


def before_after(rows: list[dict], path, title="Before and after") -> Path:
    style()
    fig, ax = plt.subplots(figsize=SIZE)
    labels = [r["metric"] for r in rows]
    ratio = [
        r["after"] / r["before"] * 100 if r["before"] else 0 for r in rows
    ]
    ax.barh(
        labels[::-1], ratio[::-1], color="#7f7f7f", edgecolor="#000000", lw=0.4
    )
    ax.axvline(100, color="#000000", lw=0.6, ls="--")
    ax.set_xlabel("After as percent of before")
    ax.set_title(title)
    return _save(fig, path)


def _group(tag: str, level: int) -> str:
    parts = tag.split("/")
    return parts[min(level, len(parts)) - 1]


# listing: chart_load_by_group
def load_by_group(
    pj: ParsedJournal,
    path,
    level: int = 2,
    title: str = "Share of annunciated alarms by area",
) -> Path:
    """Horizontal bars: each group's share of all annunciated alarms.

    Groups are a tag-path level: level 2 of RedMesa/Cryo/V-410/LIT-4101
    is Cryo. Works on any journal whose tag paths are organized by area.
    """
    from collections import Counter
    from .site import tag_of

    style()
    counts = Counter(_group(tag_of(e.source), level) for e in pj.annunciated())
    total = sum(counts.values()) or 1
    items = counts.most_common()[::-1]
    fig, ax = plt.subplots(figsize=SIZE)
    ax.barh(
        [k for k, _ in items],
        [100 * v / total for _, v in items],
        color="#7f7f7f",
        edgecolor="#000000",
        lw=0.4,
    )
    for i, (_, v) in enumerate(items):
        ax.text(100 * v / total + 0.6, i, f"{v:,}", va="center", fontsize=6.5)
    ax.set_xlabel("Percent of annunciated alarms")
    ax.set_title(title)
    ax.set_xlim(0, max(100 * v / total for _, v in items) * 1.25)
    return _save(fig, path)


# end listing


def inventory(
    site, path, title: str = "Configured alarms by area and priority"
) -> Path:
    """Stacked bars of a site model's configured alarms, by area and priority."""
    from collections import Counter
    from .site import PRIORITY_NAMES

    style()
    areas = [a for a, _ in Counter(x.area for x in site.alarms).most_common()][
        ::-1
    ]
    fills = {
        1: ("white", ""),
        2: ("#bfbfbf", ""),
        3: ("#7f7f7f", ""),
        4: ("#000000", ""),
    }
    fig, ax = plt.subplots(figsize=SIZE)
    left = [0] * len(areas)
    for p in (1, 2, 3, 4):
        vals = [
            sum(1 for x in site.alarms if x.area == a and x.priority == p)
            for a in areas
        ]
        ax.barh(
            areas,
            vals,
            left=left,
            color=fills[p][0],
            edgecolor="#000000",
            lw=0.5,
            label=PRIORITY_NAMES[p],
        )
        left = [l + v for l, v in zip(left, vals)]
    for i, total in enumerate(left):
        ax.text(total + 0.5, i, str(total), va="center", fontsize=6.5)
    ax.set_xlabel("Configured alarms")
    ax.set_title(title)
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, path)


def rows_per_day(
    events, path, restarts=(), title: str = "Journal rows per day"
) -> Path:
    """Daily row count from raw alarm_events rows, with gateway restarts marked."""
    from collections import Counter

    style()
    counts = Counter(e.eventtime.date() for e in events)
    days = sorted(counts)
    fig, ax = plt.subplots(figsize=SIZE)
    ax.bar(
        days,
        [counts[d] for d in days],
        width=1.0,
        color="#7f7f7f",
        edgecolor="none",
    )
    top = max(counts.values()) if counts else 1
    for t in restarts:
        ax.axvline(t, color="#000000", lw=0.8, ls="--")
        ax.text(
            t, top * 1.02, " restart", fontsize=6.5, va="bottom", rotation=90
        )
    ax.set_ylim(0, top * 1.25)
    ax.set_ylabel("Rows written to alarm_events")
    ax.set_title(title)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    return _save(fig, path)


def stages_chart(
    rows: list[dict], path, title: str = "What each kind of fix bought"
) -> Path:
    """Bars: alarms per day at each cumulative stage. Line: peak in 10 min."""
    style()
    fig, ax = plt.subplots(figsize=SIZE)
    labels = [r["stage"] for r in rows]
    xs = range(len(rows))
    ax.bar(
        xs,
        [r["per_day"] for r in rows],
        color="#7f7f7f",
        edgecolor="#000000",
        lw=0.4,
        label="Alarms per day, plant",
    )
    ax.set_ylabel("Annunciated alarms per day, both consoles")
    ax2 = ax.twinx()
    ax2.plot(
        xs,
        [r["peak_10min"] for r in rows],
        color="#000000",
        marker="o",
        ms=3,
        label="Peak in 10 min, worst console",
    )
    ax2.set_ylabel("Peak alarms in 10 minutes")
    ax2.spines["right"].set_visible(True)
    ax2.set_ylim(0, max(r["peak_10min"] for r in rows) * 1.15)
    ax.set_xticks(list(xs), labels, rotation=40, ha="right")
    ax.set_title(title)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper right")
    return _save(fig, path)


# listing: chart_logic_demo
def logic_demo(
    site, source: str, path, seed: int = 7, minutes: float = 12.0
) -> Path:
    """One chattering window run through the as-found and rationalized
    alarm logic: the same PV, two configurations, two activation counts."""
    import random

    from .generator import ALL_FIXES, _chatter_window

    style()
    a = site.by_source()[source]
    sig = site.signals[source]
    runs = {}
    for label, fixes in (
        ("As found", set()),
        ("Rationalized", set(ALL_FIXES)),
    ):
        rng = random.Random(seed)  # same noise for both runs
        runs[label] = _chatter_window(rng, a, sig, 0.0, minutes, fixes)
    rng = random.Random(seed)
    from .generator import _ar1
    import math

    n = int(minutes * 60)
    noise = _ar1(rng, n, sig["sigma"])
    sign = 1 if a.name.startswith("H") else -1
    pv = [
        a.setpoint
        + sign * sig["sigma"] * 1.2 * math.sin(math.pi * i / n)
        - sign * 0.3 * sig["sigma"]
        + e
        for i, e in enumerate(noise)
    ]
    fig, (top, mid, bot) = plt.subplots(
        3,
        1,
        figsize=SIZE,
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1, 1]},
    )
    t = [i / 60 for i in range(n)]
    top.plot(t, pv, color="#000000", lw=0.6)
    top.axhline(a.setpoint, color="#000000", lw=0.8, ls="--")
    db = a.rat.deadband
    top.axhspan(a.setpoint - db, a.setpoint, color="#d9d9d9", lw=0)
    top.set_ylabel(f"{a.units}")
    top.set_title(f"{a.displaypath}: one window, two configurations")
    top.text(
        t[-1], a.setpoint, " setpoint", fontsize=6.5, va="bottom", ha="right"
    )
    for ax, (label, acts) in zip((mid, bot), runs.items()):
        for x in acts:
            ax.axvspan(x.t_on / 60, (x.t_off or n) / 60, color="#000000", lw=0)
        ax.set_yticks([])
        ax.set_ylabel(
            f"{label}\n{len(acts)} alarms",
            rotation=0,
            ha="right",
            va="center",
            fontsize=7,
        )
    bot.set_xlabel("Minutes")
    return _save(fig, path)


# end listing


def cascade(site, upset_name: str, path, title: str | None = None) -> Path:
    """Each cascade step of one upset as its window after the trip.

    Hatched bars are the steps rationalization later suppresses by state.
    """
    style()
    up = next(u for u in site.upsets if u.name == upset_name)
    by = site.by_source()
    steps = sorted(up.cascade, key=lambda s: s.min_s)
    fig, ax = plt.subplots(figsize=SIZE)
    for i, st in enumerate(reversed(steps)):
        a = by[st.alarm]
        sup = up.state in a.rat.suppress_in
        ax.barh(
            i,
            (st.max_s - st.min_s) / 60,
            left=st.min_s / 60,
            color="white" if sup else "#7f7f7f",
            edgecolor="#000000",
            hatch="////" if sup else "",
            lw=0.5,
        )
        label = a.displaypath + ("" if st.p >= 1 else f" (p {st.p:.1f})")
        ax.text(-0.3, i, label, ha="right", va="center", fontsize=5.5)
    ax.set_yticks([])
    ax.set_xlim(0, max(s.max_s for s in steps) / 60 * 1.05)
    ax.set_xlabel(f"Minutes after {by[up.initiator].displaypath}")
    ax.set_title(title or f"{upset_name}: the modeled cascade")
    fig.subplots_adjust(left=0.45)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def _log_hist(ax, values, edges, labels):
    bins = [0] * (len(edges) - 1)
    for v in values:
        for i in range(len(edges) - 1):
            if edges[i] <= v < edges[i + 1]:
                bins[i] += 1
                break
    total = sum(bins) or 1
    ax.bar(
        labels,
        [100 * b / total for b in bins],
        color="#7f7f7f",
        edgecolor="#000000",
        lw=0.4,
    )
    ax.set_ylabel("Percent of episodes")


# listing: chart_durations
def duration_histogram(
    pj: ParsedJournal, path, title: str = "How long alarms stay active"
) -> Path:
    """Time from active to clear, on a log scale of bins."""
    style()
    edges = [0, 1, 5, 10, 60, 600, 3600, 86400, 1e12]
    labels = [
        "<1 s",
        "1-5 s",
        "5-10 s",
        "10-60 s",
        "1-10 min",
        "10-60 min",
        "1-24 h",
        ">24 h",
    ]
    vals = [e.duration(pj.end) for e in pj.annunciated() if e.clear]
    fig, ax = plt.subplots(figsize=SIZE)
    _log_hist(ax, vals, edges, labels)
    ax.set_xticks(range(len(labels)), labels, rotation=40, ha="right")
    ax.set_title(title)
    return _save(fig, path)


# end listing


def ack_histogram(
    pj: ParsedJournal, path, title: str = "Time to acknowledge"
) -> Path:
    """Time from active to acknowledgement, split by whether the alarm
    had already cleared when it was acknowledged."""
    style()
    edges = [0, 10, 30, 60, 300, 900, 3600, 1e12]
    labels = [
        "<10 s",
        "10-30 s",
        "30-60 s",
        "1-5 min",
        "5-15 min",
        "15-60 min",
        ">1 h",
    ]
    eps = [e for e in pj.annunciated() if e.ack]
    fig, ax = plt.subplots(figsize=SIZE)
    import numpy as np

    xs = np.arange(len(labels))
    for k, (name, pick, fill) in enumerate(
        (
            (
                "Still active",
                lambda e: e.clear is None or e.ack <= e.clear,
                "#000000",
            ),
            (
                "Already cleared",
                lambda e: e.clear is not None and e.ack > e.clear,
                "#bfbfbf",
            ),
        )
    ):
        vals = [e.time_to_ack() for e in eps if pick(e)]
        bins = [
            sum(1 for v in vals if edges[i] <= v < edges[i + 1])
            for i in range(len(labels))
        ]
        ax.bar(
            xs + (k - 0.5) * 0.4,
            [100 * b / len(eps) for b in bins],
            0.4,
            color=fill,
            edgecolor="#000000",
            lw=0.4,
            label=f"{name} ({100 * len(vals) / len(eps):.0f}%)",
        )
    ax.set_xticks(xs, labels, rotation=40, ha="right")
    ax.set_ylabel("Percent of acknowledged episodes")
    ax.set_title(title)
    ax.legend(frameon=False)
    return _save(fig, path)


def monthly_trend(
    rows_by_console: dict[str, list[dict]], path, title: str = "Month by month"
) -> Path:
    """Two panels: average per 10 min and time in flood, per console."""
    style()
    fig, (top, bot) = plt.subplots(2, 1, figsize=SIZE, sharex=True)
    for i, (c, rows) in enumerate(rows_by_console.items()):
        xs = [r["month"][5:] for r in rows]
        top.plot(
            xs,
            [r["per_10min"] for r in rows],
            color=INK[i % 4],
            ls=DASH[i % 4],
            marker="o",
            ms=3,
            label=f"Console {c}",
        )
        bot.plot(
            xs,
            [r["pct_time_in_flood"] for r in rows],
            color=INK[i % 4],
            ls=DASH[i % 4],
            marker="o",
            ms=3,
        )
    top.axhline(2, color="#000000", lw=0.6, ls=":")
    top.text(0, 2, " 2 per 10 min", fontsize=6.5, va="bottom")
    top.set_ylabel("Average per 10 min")
    top.set_ylim(0, None)
    top.legend(frameon=False, loc="lower right")
    top.set_title(title)
    bot.axhline(1, color="#000000", lw=0.6, ls=":")
    bot.text(0, 1, " 1% target", fontsize=6.5, va="bottom")
    bot.set_ylabel("Time in flood, %")
    bot.set_ylim(0, None)
    bot.set_xlabel("Month")
    return _save(fig, path)


def hour_of_day(
    pj: ParsedJournal,
    path,
    consoles=None,
    title: str = "Alarms by hour of day",
) -> Path:
    """Average annunciated alarms in each clock hour, per console."""
    style()
    consoles = consoles or pj.consoles()
    fig, ax = plt.subplots(figsize=SIZE)
    for i, c in enumerate(consoles):
        counts = [0] * 24
        for e in pj.annunciated():
            if e.console == c:
                counts[e.active.hour] += 1
        ax.plot(
            range(24),
            [n / pj.days for n in counts],
            color=INK[i % 4],
            ls=DASH[i % 4],
            marker="o",
            ms=2.5,
            label=f"Console {c}",
        )
    for h in (6, 18):
        ax.axvline(h, color="#000000", lw=0.6, ls=":")
    ax.text(
        12, ax.get_ylim()[1] * 0.02, "day shift", ha="center", fontsize=6.5
    )
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Average alarms in the hour")
    ax.set_ylim(0, None)
    ax.set_title(title)
    ax.legend(frameon=False)
    return _save(fig, path)


def flood_sizes(floods, path, title: str = "Floods by size and kind") -> Path:
    """Stacked bars: floods by number of alarms, split by kind."""
    from .floods import classify

    style()
    edges = [11, 20, 30, 50, 100, 10**9]
    labels = ["11-19", "20-29", "30-49", "50-99", "100+"]
    fig, ax = plt.subplots(figsize=SIZE)
    base = [0] * len(labels)
    kinds = (
        ("single alarm", "#bfbfbf"),
        ("several alarms", "#ffffff"),
        ("upset + chatter", "#7f7f7f"),
        ("upset", "#000000"),
    )
    for kind, fill in kinds:
        vals = [
            sum(
                1
                for f in floods
                if classify(f) == kind and edges[i] <= f.count < edges[i + 1]
            )
            for i in range(len(labels))
        ]
        n = sum(vals)
        ax.bar(
            labels,
            vals,
            bottom=base,
            color=fill,
            edgecolor="#000000",
            lw=0.4,
            label=f"{kind.capitalize()} ({n})",
        )
        base = [b + v for b, v in zip(base, vals)]
    ax.set_xlabel("Alarms in the flood")
    ax.set_ylabel("Number of floods")
    ax.set_title(title)
    ax.legend(frameon=False)
    return _save(fig, path)


def first_outs(
    floods, path, top: int = 8, title: str = "What starts the floods"
) -> Path:
    """Horizontal bars: the most common first alarm of a flood."""
    from collections import Counter

    style()
    c = Counter(f.episodes[0].displaypath for f in floods if f.episodes)
    items = c.most_common(top)[::-1]
    fig, ax = plt.subplots(figsize=SIZE)
    ax.barh(
        [k for k, _ in items],
        [v for _, v in items],
        color="#7f7f7f",
        edgecolor="#000000",
        lw=0.4,
    )
    for i, (_, v) in enumerate(items):
        ax.text(v + 0.3, i, str(v), va="center", fontsize=6.5)
    ax.set_xlabel("Floods started")
    ax.set_title(title)
    return _save(fig, path)
