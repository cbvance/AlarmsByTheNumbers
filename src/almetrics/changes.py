"""The configuration changes a completed MADB asks for.

Compares each alarm's as-found configuration with the team's decisions
and writes two things: a change list for the management of change
record, and the alarm settings in Ignition's tag JSON names, ready for
system.tag.configure or a tag import.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .madb import PRIORITY_VALUE, Decision
from .site import PRIORITY_NAMES, Site

MODE = {
    "H": "AboveValue",
    "HH": "AboveValue",
    "L": "BelowValue",
    "LL": "BelowValue",
}


@dataclass
class Change:
    tag: str
    alarm: str
    field: str
    old: object
    new: object


# listing: change_list
def change_list(site: Site, decisions: list[Decision]) -> list[Change]:
    """Every property the team's decisions change, alarm by alarm."""
    by_disp = {d.displaypath: d for d in decisions}
    out = []
    for a in site.alarms:
        d = by_disp.get(a.displaypath)
        if d is None or d.get("Keep or Remove") is None:
            continue
        if d.get("Keep or Remove") == "Remove":
            out.append(Change(a.tag, a.name, "remove", "configured", "delete"))
            continue
        new = {
            "priority": d.get("Rationalized Priority"),
            "setpointA": d.get("Setpoint"),
            "deadband": d.get("Deadband") or 0,
            "timeOnDelaySeconds": d.get("On Delay (s)") or 0,
            "timeOffDelaySeconds": d.get("Off Delay (s)") or 0,
        }
        old = {
            "priority": PRIORITY_NAMES[a.priority],
            "setpointA": a.setpoint,
            "deadband": 0,
            "timeOnDelaySeconds": 0,
            "timeOffDelaySeconds": 0,
        }
        for f, v in new.items():
            if v is not None and v != old[f]:
                out.append(Change(a.tag, a.name, f, old[f], v))
        if d.get("Suppress In State"):
            out.append(
                Change(
                    a.tag,
                    a.name,
                    "enabled",
                    True,
                    f"by state: {d.get('Suppress In State')}",
                )
            )
    return out


def alarm_json(a, d: Decision) -> dict:
    """One alarm in Ignition's tag JSON names, as the team decided it."""
    cfg = {
        "name": a.name,
        "mode": MODE.get(a.name, "Equality"),
        "setpointA": float(d.get("Setpoint") or a.setpoint),
        "priority": d.get("Rationalized Priority")
        or PRIORITY_NAMES[a.priority],
        "deadband": float(d.get("Deadband") or 0),
        "deadbandMode": "Absolute",
        "timeOnDelaySeconds": float(d.get("On Delay (s)") or 0),
        "timeOffDelaySeconds": float(d.get("Off Delay (s)") or 0),
        "displayPath": a.displaypath,
        "notes": " | ".join(
            f"{k}: {d.get(k)}"
            for k in ("Cause", "Consequence", "Corrective Action")
            if d.get(k)
        ),
    }
    assert cfg["priority"] in PRIORITY_VALUE or cfg["priority"] == "No alarm"
    states = [
        x.strip()
        for x in (d.get("Suppress In State") or "").split(",")
        if x.strip()
    ]
    if states:
        from .states import enabled_binding

        cfg["enabled"] = enabled_binding(states, a.tag.split("/", 1)[0])
    return cfg


# end listing


def tag_patch(site: Site, decisions: list[Decision]) -> dict[str, list]:
    """Kept alarms grouped by tag and folder, every alarm on a changed tag
    written in full so nothing on the tag is left to a default."""
    by_disp = {d.displaypath: d for d in decisions}
    tags: dict[str, list] = {}
    for a in site.alarms:
        d = by_disp.get(a.displaypath)
        if d is None or d.get("Keep or Remove") != "Keep":
            continue
        tags.setdefault(a.tag, []).append(alarm_json(a, d))
    folders: dict[str, list] = {}
    for tag, alarms in sorted(tags.items()):
        folder, name = tag.rsplit("/", 1)
        folders.setdefault(folder, []).append({"name": name, "alarms": alarms})
    return folders


def write_changes(
    site: Site, decisions: list[Decision], outdir: str | Path
) -> dict[str, Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    changes = change_list(site, decisions)
    with open(outdir / "changes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Tag", "Alarm", "Property", "As found", "Rationalized"])
        for c in changes:
            w.writerow([c.tag, c.alarm, c.field, c.old, c.new])
    (outdir / "tag_patch.json").write_text(
        json.dumps(tag_patch(site, decisions), indent=2)
    )
    from .states import state_tags

    root = site.alarms[0].tag.split("/", 1)[0]
    (outdir / "state_tags.json").write_text(
        json.dumps(state_tags(site, root), indent=2)
    )
    return {
        "changes": outdir / "changes.csv",
        "patch": outdir / "tag_patch.json",
        "states": outdir / "state_tags.json",
    }
