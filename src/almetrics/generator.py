"""Generate a synthetic alarm journal in the Ignition 8.1 table layout.

The generator does not invent alarm counts directly. It models the
process conditions behind each alarm (genuine excursions, a noisy level
hovering at its setpoint, spikes on a vibration probe, equipment left
out of service, plant trips that cascade) and runs every condition
through the same alarm logic Ignition applies: setpoint, deadband, on
delay, off delay, enabled state, shelving. The fixes the book makes are
changes to that configuration, so a regenerated journal improves for the
same reasons a real one would.

Fixes (combine any; "all" applies every one):
  deadband   rationalized deadbands and on/off delays
  setpoint   setpoints moved outside the normal operating swing
  priority   rationalized priorities
  remove     delete alarms that are not alarms (equipment status)
  state      state-based suppression of predictable trip consequences
  stale      repair the conditions behind stale alarms
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .journal import (
    ACK,
    ACTIVE,
    CLEAR,
    DISABLED,
    ENABLED,
    FLAG_ACKED,
    FLAG_CLEARED,
    FLAG_ENABLED,
    FLAG_SHELVED,
    FLAG_SYS_ACK,
    FLAG_SYSTEM,
    JournalWriter,
)
from .site import AlarmDef, Site

ALL_FIXES = ("deadband", "setpoint", "priority", "remove", "state", "stale")


@dataclass
class Activation:
    alarm: AlarmDef
    t_on: float  # seconds from start of window
    t_off: float | None  # None: still active at end of window
    value: float
    shelved: bool = False
    in_upset: bool = False


# listing: evaluate_alarm
def evaluate(
    pv: list[float],
    t0: float,
    high: bool,
    setpoint: float,
    deadband: float,
    on_delay: float,
    off_delay: float,
    dt: float = 1.0,
) -> list[tuple[float, float, float]]:
    """Run a sampled PV through Ignition-style alarm logic.

    Returns (t_on, t_off, value_at_on) for each activation. The condition
    must hold for on_delay before the alarm goes active, and the PV must
    return past setpoint minus deadband (plus deadband for a low alarm)
    for off_delay before it clears.
    """
    out = []
    active = False
    since = None  # time the pending transition started
    t_on = v_on = 0.0
    for i, v in enumerate(pv):
        t = t0 + i * dt
        if not active:
            cond = v > setpoint if high else v < setpoint
            if cond:
                since = t if since is None else since
                if t - since >= on_delay:
                    active, t_on, v_on, since = True, t, v, None
            else:
                since = None
        else:
            back = v < setpoint - deadband if high else v > setpoint + deadband
            if back:
                since = t if since is None else since
                if t - since >= off_delay:
                    out.append((t_on, t, v_on))
                    active, since = False, None
            else:
                since = None
    if active:
        out.append((t_on, t0 + len(pv) * dt, v_on))
    return out


# end listing


def _is_high(alarm: AlarmDef) -> bool:
    return alarm.name.startswith("H")


def _cfg(alarm: AlarmDef, fixes: set[str]) -> tuple[float, float, float]:
    if "deadband" in fixes:
        return alarm.rat.deadband, alarm.rat.on_delay, alarm.rat.off_delay
    return 0.0, 0.0, 0.0


def _ar1(
    rng: random.Random, n: int, sigma: float, phi: float = 0.9
) -> list[float]:
    """Correlated noise, like a real transmitter signal sampled at 1 s."""
    scale = sigma * math.sqrt(1 - phi * phi)
    x, out = rng.gauss(0, sigma), []
    for _ in range(n):
        x = phi * x + rng.gauss(0, scale)
        out.append(x)
    return out


def _chatter_window(
    rng, alarm, sig, t_start, minutes, fixes
) -> list[Activation]:
    n = int(minutes * 60)
    noise = _ar1(rng, n, sig["sigma"])
    sign = 1 if _is_high(alarm) else -1
    # mean drifts slowly across the setpoint and back
    drift = [
        sign * sig["sigma"] * 1.2 * math.sin(math.pi * i / n)
        - sign * 0.3 * sig["sigma"]
        for i in range(n)
    ]
    pv = [alarm.setpoint + d + e for d, e in zip(drift, noise)]
    db, on_d, off_d = _cfg(alarm, fixes)
    return [
        Activation(alarm, a, b, v)
        for a, b, v in evaluate(
            pv, t_start, _is_high(alarm), alarm.setpoint, db, on_d, off_d
        )
    ]


def _excursion_value(rng, alarm) -> float:
    span = max(abs(alarm.setpoint) * 0.05, 1.0)
    bump = abs(rng.gauss(0, span * 0.3)) + 0.01 * span
    return round(alarm.setpoint + (bump if _is_high(alarm) else -bump), 3)


# listing: generate
def generate(
    site: Site,
    db_path: str | Path,
    start: datetime,
    days: int,
    fixes: set[str] | tuple[str, ...] = (),
    seed: int = 1843,
) -> dict:
    """Write a synthetic journal and return a summary of what was planted."""
    fixes = set(ALL_FIXES) if "all" in fixes else set(fixes)
    rng = random.Random(seed)
    horizon = days * 86400.0
    acts: dict[str, list[Activation]] = {a.source: [] for a in site.alarms}
    by_src = site.by_source()
    live = {
        a.source
        for a in site.alarms
        if not ("remove" in fixes and a.rat.remove)
    }
    toggles: list[tuple[float, AlarmDef, int]] = (
        []
    )  # (time, alarm, ENABLED/DISABLED)
    planted = {"upsets": [], "chatter_windows": 0, "fleeting_spikes": 0}

    # Every random draw below happens whatever fixes are applied, so the
    # process conditions (when excursions, windows, spikes, stale spans,
    # and upsets occur) are identical at every stage. Fixes decide only
    # what becomes an alarm. Toggle times use their own stream for the
    # same reason.
    toggle_rng = random.Random(seed + 1)

    # 1. genuine excursions on every alarm
    for a in site.alarms:
        if a.rate <= 0:
            continue
        keep_ratio = 1.0
        if "setpoint" in fixes and a.rat.rate is not None:
            keep_ratio = a.rat.rate / a.rate
        n = _poisson(rng, a.rate * days)
        db, on_d, off_d = _cfg(a, fixes)
        for i in range(n):
            t = rng.uniform(0, horizon)
            dur = rng.lognormvariate(math.log(240), 1.0)
            value = _excursion_value(rng, a)
            # moving a setpoint out of the normal swing thins excursions
            kept = int((i + 1) * keep_ratio) > int(i * keep_ratio)
            ok = a.source in live and kept and dur > on_d
            if ok:
                acts[a.source].append(
                    Activation(a, t + on_d, t + dur + off_d, value)
                )
            # with no deadband, the return through setpoint rattles
            if rng.random() < 0.12:
                tt = t + dur
                for _ in range(rng.randint(1, 2)):
                    tt += rng.uniform(3, 25)
                    rattle = Activation(
                        a,
                        tt,
                        tt + rng.uniform(1, 12),
                        _excursion_value(rng, a),
                    )
                    if ok and db == 0:
                        acts[a.source].append(rattle)
                    tt += 12

    # 2. chattering and fleeting signals
    for src, sig in site.signals.items():
        a = by_src[src]
        if "sigma" in sig:
            for _ in range(_poisson(rng, sig["windows"] * days)):
                t = rng.uniform(0, horizon)
                mins = rng.uniform(*sig["minutes"])
                window = _chatter_window(rng, a, sig, t, mins, fixes)
                if src in live:
                    acts[src].extend(window)
                    planted["chatter_windows"] += 1
        else:
            db, on_d, off_d = _cfg(a, fixes)
            for _ in range(_poisson(rng, sig["spikes"] * days)):
                t = rng.uniform(0, horizon)
                dur = rng.expovariate(1 / sig["mean_s"])
                value = _excursion_value(rng, a)
                planted["fleeting_spikes"] += 1
                if src in live and dur > on_d:
                    acts[src].append(
                        Activation(a, t + on_d, t + dur + off_d, value)
                    )

    # 3. stale conditions: out-of-service equipment, failed analyzers
    for src, spans in site.stale_periods.items():
        a = by_src[src]
        for d0, d1 in spans:
            t_on, t_off = d0 * 86400.0, d1 * 86400.0
            if t_on >= horizon:
                continue
            act = Activation(
                a,
                t_on + rng.uniform(0, 600),
                None if t_off >= horizon else t_off,
                _excursion_value(rng, a),
            )
            if "stale" not in fixes and src in live:
                acts[src].append(act)

    # 4. plant upsets and their cascades
    starts = []
    for up in site.upsets:
        for _ in range(_poisson(rng, up.per_month * days / 30.0)):
            starts.append((rng.uniform(3600, horizon - 3600), up))
    starts.sort(key=lambda s: s[0])
    last_end = -1e9
    for t0, up in starts:
        if t0 < last_end + 6 * 3600:
            continue
        dur = rng.uniform(*up.duration_h) * 3600
        last_end = t0 + dur
        planted["upsets"].append((up.name, t0))
        ini = by_src[up.initiator]
        acts[ini.source].append(
            Activation(ini, t0, t0 + dur, 1.0, in_upset=True)
        )
        for step in up.cascade:
            a = by_src[step.alarm]
            if rng.random() > step.p:
                continue
            t = t0 + rng.uniform(step.min_s, step.max_s)
            if a.behavior == "chatter" and a.source in site.signals:
                new = _chatter_window(
                    rng,
                    a,
                    site.signals[a.source],
                    t,
                    rng.uniform(6, 15),
                    fixes,
                )
            else:
                off = t + rng.uniform(0.3, 1.0) * max(dur - (t - t0), 300)
                new = [Activation(a, t, off, _excursion_value(rng, a))]
            if a.source not in live:
                continue
            if "state" in fixes and up.state in a.rat.suppress_in:
                toggles.append(
                    (t0 + toggle_rng.uniform(0.2, 1.5), a, DISABLED)
                )
                toggles.append(
                    (t0 + dur + toggle_rng.uniform(1, 30), a, ENABLED)
                )
                continue
            for act in new:
                act.in_upset = True
                acts[a.source].append(act)

    # 5. merge overlaps per alarm, then shelving by the operators
    for src, lst in acts.items():
        lst.sort(key=lambda x: x.t_on)
        merged: list[Activation] = []
        for x in lst:
            if x.t_on >= horizon:
                continue
            if merged and (
                merged[-1].t_off is None or x.t_on <= merged[-1].t_off
            ):
                prev = merged[-1]
                if prev.t_off is not None and (
                    x.t_off is None or x.t_off > prev.t_off
                ):
                    prev.t_off = x.t_off
                continue
            if x.t_off is not None and x.t_off >= horizon:
                x.t_off = None
            merged.append(x)
        acts[src] = merged
        if by_src[src].behavior == "chatter":
            _shelve(rng, merged, 0.01 if "deadband" in fixes else 0.06)

    summary = _write(
        site, db_path, start, horizon, acts, toggles, fixes, rng, live
    )
    summary.update(planted)
    return summary


# end listing


def _shelve(rng, lst: list[Activation], p: float) -> None:
    """Operators shelve a chattering alarm for a shift, sometimes."""
    until = -1.0
    burst = 0
    for i, x in enumerate(lst):
        if x.t_on < until:
            x.shelved = True
            continue
        burst = burst + 1 if i and x.t_on - lst[i - 1].t_on < 120 else 0
        if burst == 5 and rng.random() < p:
            until = x.t_on + rng.choice((1, 2, 4)) * 3600


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 50:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    k, p, L = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def _uuid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def seed_restart(rng: random.Random) -> int:
    """A seed for restart artifacts that leaves the main stream untouched."""
    return rng.getstate()[1][0]


def _active_at(lst: list[Activation], t: float) -> bool:
    return any(x.t_on <= t and (x.t_off is None or x.t_off > t) for x in lst)


def _write(
    site, db_path, start, horizon, acts, toggles, fixes, rng, live=None
) -> dict:
    live = live if live is not None else {a.source for a in site.alarms}
    rows = []  # (t, order, kind, payload)
    for src, lst in acts.items():
        for x in lst:
            rows.append((x.t_on, 0, "on", x))
    rows.sort(key=lambda r: (r[0], r[1]))

    w = JournalWriter(db_path)
    out_rows = []  # (t, eventid, alarm, type, flags, props)
    n_act = 0
    for t_on, _, _, x in rows:
        a = x.alarm
        eid = _uuid(rng)
        pri = (
            a.rat.priority
            if ("priority" in fixes and a.rat.priority is not None)
            else a.priority
        )
        shelf = FLAG_SHELVED if x.shelved else 0
        props = {"setpointA": float(a.setpoint), "eventValue": float(x.value)}
        out_rows.append((t_on, eid, a, pri, ACTIVE, shelf, props))
        n_act += 1
        t_ack = None
        if not x.shelved:
            delay = rng.lognormvariate(math.log(20), 0.9)
            if x.in_upset:
                delay += rng.uniform(60, 900)
            t_ack = t_on + delay
            if t_ack >= horizon:
                t_ack = None
        if x.t_off is not None:
            flags = (
                FLAG_CLEARED
                | shelf
                | (FLAG_ACKED if t_ack is not None and t_ack <= x.t_off else 0)
            )
            out_rows.append(
                (
                    x.t_off,
                    eid,
                    a,
                    pri,
                    CLEAR,
                    flags,
                    {"eventValue": float(a.setpoint)},
                )
            )
        if t_ack is not None:
            flags = (
                FLAG_CLEARED if x.t_off is not None and x.t_off < t_ack else 0
            )
            hour = (start + timedelta(seconds=t_ack)).hour
            day_user, night_user = site.operators[a.console]
            out_rows.append(
                (
                    t_ack,
                    eid,
                    a,
                    pri,
                    ACK,
                    flags,
                    {"ackUser": day_user if 6 <= hour < 18 else night_user},
                )
            )
    for t, a, kind in toggles:
        if t < horizon:
            pri = (
                a.rat.priority
                if ("priority" in fixes and a.rat.priority is not None)
                else a.priority
            )
            out_rows.append((t, _uuid(rng), a, pri, kind, FLAG_ENABLED, {}))
    # listing: restart_rows
    # two gateway restarts in the window, as a real journal would show them:
    # shutdown and startup system rows, then a clear row flagged system-ack,
    # acked, and cleared (28) for every alarm that is not active at startup.
    # These clears have no active row: the parser counts them as orphans.
    rr = random.Random(seed_restart(rng))
    for _ in range(2):
        t = rng.uniform(0, horizon - 600)
        up = t + rng.uniform(90, 240)
        out_rows.append(
            (t, _uuid(rng), "System Shutdown", 0, ACTIVE, FLAG_SYSTEM, {})
        )
        out_rows.append(
            (up, _uuid(rng), "System Startup", 0, ACTIVE, FLAG_SYSTEM, {})
        )
        for a in site.alarms:
            if a.source in live and not _active_at(acts.get(a.source, []), up):
                pri = (
                    a.rat.priority
                    if ("priority" in fixes and a.rat.priority is not None)
                    else a.priority
                )
                out_rows.append(
                    (
                        up + rr.uniform(0.5, 5),
                        _uuid(rr),
                        a,
                        pri,
                        CLEAR,
                        FLAG_SYS_ACK | FLAG_ACKED | FLAG_CLEARED,
                        {},
                    )
                )
    # end listing

    out_rows.sort(key=lambda r: (r[0], r[4]))
    for t, eid, a, pri, etype, flags, props in out_rows:
        src, disp = (a, a) if isinstance(a, str) else (a.source, a.displaypath)
        w.add(
            eid,
            src,
            disp,
            pri,
            etype,
            flags,
            start + timedelta(seconds=t),
            props,
        )
    w.close()
    return {
        "db": str(db_path),
        "activations": n_act,
        "rows": w.next_id - 1,
        "fixes": sorted(fixes),
        "start": start.isoformat(),
        "days": horizon / 86400,
    }
