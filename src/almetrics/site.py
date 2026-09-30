"""Site model: alarm definitions, upset scenarios, and console mapping.

A site is plain data. The generator reads the whole model. The analysis
tools only need the console map, so they also run against a real plant
journal where no site module exists.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

PRIORITY_NAMES = {
    0: "Diagnostic",
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Critical",
}


# listing: alarm_def
@dataclass(frozen=True)
class Rationalized:
    """The configuration an alarm carries after rationalization."""

    priority: int | None = None  # None keeps the as-found priority
    deadband: float = 0.0  # engineering units
    on_delay: float = 0.0  # seconds the condition must hold
    off_delay: float = 0.0  # seconds the return must hold
    remove: bool = False  # not an alarm; delete it
    rate: float | None = None  # excursions/day once the setpoint moves
    suppress_in: tuple[str, ...] = ()  # plant states that disable it


@dataclass(frozen=True)
class AlarmDef:
    tag: str  # tag path under the provider
    name: str  # alarm name on the tag, e.g. "Hi"
    area: str
    console: str
    description: str
    priority: int  # as found
    setpoint: float
    units: str
    behavior: str  # normal, chatter, fleeting, stale, status, consequence
    rate: float  # genuine excursions per day
    rat: Rationalized = field(default_factory=Rationalized)

    @property
    def source(self) -> str:
        return f"prov:default:/tag:{self.tag}:/alm:{self.name}"

    @property
    def displaypath(self) -> str:
        return f"{self.description} {self.name}"


# end listing


@dataclass(frozen=True)
class CascadeStep:
    alarm: str  # source path of the alarm that follows
    min_s: float  # earliest seconds after the trip
    max_s: float  # latest seconds after the trip
    p: float = 1.0  # probability it fires in a given upset


@dataclass(frozen=True)
class Upset:
    name: str
    state: str  # plant state entered by the trip
    per_month: float  # expected occurrences per 30 days
    duration_h: tuple[float, float]  # time in the state before restart
    initiator: str  # first-out alarm source
    cascade: tuple[CascadeStep, ...]


@dataclass
class Site:
    name: str
    alarms: list[AlarmDef]
    upsets: list[Upset]
    consoles: dict[str, str]  # tag prefix -> console
    operators: dict[str, tuple[str, str]]  # console -> (day user, night user)
    signals: dict[str, dict] = field(
        default_factory=dict
    )  # per-source noise model
    stale_periods: dict[str, list[tuple[float, float]]] = field(
        default_factory=dict
    )

    def by_source(self) -> dict[str, AlarmDef]:
        return {a.source: a for a in self.alarms}


def tag_of(source: str) -> str:
    """Return the tag path inside an Ignition qualified source path."""
    if ":/tag:" in source:
        rest = source.split(":/tag:", 1)[1]
        return rest.split(":/alm:", 1)[0]
    return source


class ConsoleMap:
    """Map an alarm source to an operator console by tag-path prefix."""

    def __init__(
        self, prefixes: dict[str, str] | None = None, default: str = "ALL"
    ):
        # longest prefix wins
        self.rules = sorted(
            (prefixes or {}).items(), key=lambda kv: -len(kv[0])
        )
        self.default = default

    def console(self, source: str) -> str:
        tag = tag_of(source)
        for prefix, con in self.rules:
            if tag.startswith(prefix):
                return con
        return self.default

    @classmethod
    def from_csv(cls, path: str | Path) -> "ConsoleMap":
        """Read a two-column CSV: prefix,console."""
        rules = {}
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rules[row["prefix"].strip()] = row["console"].strip()
        return cls(rules)
