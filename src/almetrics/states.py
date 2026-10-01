"""Plant states for state-based alarming, and their Ignition form.

Each upset in the site model names a plant state. The state is true while
the upset's initiating condition holds; every alarm the team marked to
suppress in that state has its Enabled property bound to the inverse.
"""

from __future__ import annotations

from .site import Site

STATE_FOLDER = "States"
PROVIDER = "default"


def _condition(a, provider: str = PROVIDER) -> str:
    """The initiating alarm's condition as an Ignition expression."""
    ref = f"{{[{provider}]{a.tag}}}"
    if a.name in ("H", "HH"):
        return f"{ref} > {a.setpoint:g}"
    if a.name in ("L", "LL"):
        return f"{ref} < {a.setpoint:g}"
    return f"{ref} = {a.setpoint:g}"


# listing: state_tags
def state_tags(site: Site, root: str, provider: str = PROVIDER) -> dict:
    """One Boolean expression tag per plant state, true while the state's
    initiating condition holds."""
    by = site.by_source()
    tags = []
    for u in site.upsets:
        a = by[u.initiator]
        tags.append(
            {
                "name": u.state,
                "tagType": "AtomicTag",
                "valueSource": "expr",
                "dataType": "Boolean",
                "expression": _condition(a, provider),
                "documentation": f"{u.name}: true while {a.displaypath} holds",
            }
        )
    return {f"{root}/{STATE_FOLDER}": tags}


def enabled_binding(states, root: str, provider: str = PROVIDER) -> dict:
    """The Enabled property of an alarm suppressed in these states."""
    refs = " || ".join(
        f"{{[{provider}]{root}/{STATE_FOLDER}/{s}}}" for s in states
    )
    return {"bindType": "Expression", "value": f"!({refs})"}


# end listing


# listing: first_ten
def first_ten(
    pj, initiator: str, console: str | None = None, minutes: float = 10.0
) -> list[tuple]:
    """For every activation of an upset's initiating alarm, the alarms the
    operator received in the following minutes (initiator included).

    The EEMUA benchmark from Chapter 4 asks for fewer than ten in the
    first ten minutes after a major upset."""
    from datetime import timedelta

    ann = [
        e for e in pj.annunciated() if console is None or e.console == console
    ]
    starts = sorted(e.active for e in ann if e.source == initiator)
    out = []
    for t in starts:
        end = t + timedelta(minutes=minutes)
        out.append((t, sum(1 for e in ann if t <= e.active < end)))
    return out


# end listing
