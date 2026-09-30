"""Apply the Red Mesa fixes one kind at a time and measure each stage.

Every stage regenerates the same six months from the same seed, so the
process conditions are identical and only the alarm configuration
changes. The differences between stages are what each fix bought.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from .episodes import parse_journal
from .generator import generate
from .journal import load_events
from .metrics import console_metrics
from .nuisance import find_chattering
from .site import ConsoleMap, Site

# listing: stage_order
STAGES = [
    ("As found", ()),
    ("+ deadband and delay", ("deadband",)),
    ("+ setpoints moved", ("deadband", "setpoint")),
    ("+ status removed", ("deadband", "setpoint", "remove")),
    ("+ state-based", ("deadband", "setpoint", "remove", "state")),
    ("+ stale repaired", ("deadband", "setpoint", "remove", "state", "stale")),
    (
        "+ priorities",
        ("deadband", "setpoint", "remove", "state", "stale", "priority"),
    ),
]
# end listing


def run_stages(
    site: Site, start: datetime, days: int, seed: int = 1843, stages=STAGES
) -> list[dict]:
    cmap = ConsoleMap(site.consoles)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, fixes in stages:
            db = Path(tmp) / "stage.db"
            generate(site, db, start, days, fixes, seed)
            pj = parse_journal(load_events(db), cmap)
            ms = [console_metrics(pj, c) for c in pj.consoles()]
            allm = console_metrics(pj)
            rows.append(
                {
                    "stage": name,
                    "per_day": allm["per_day"],
                    "peak_10min": max(m["max_10min"] for m in ms),
                    "time_in_flood": max(m["pct_time_in_flood"] for m in ms),
                    "high_pct": allm["priority_mix"]["High"],
                    "chattering": len(find_chattering(pj.annunciated())),
                }
            )
    return rows
