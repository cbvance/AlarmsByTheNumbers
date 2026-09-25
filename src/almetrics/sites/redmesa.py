"""Red Mesa Gas Plant: the reference site carried through the book.

A cryogenic processing plant with inlet separation, amine treating,
molecular sieve dehydration, a turboexpander cryo section, residue
compression, and a flare. Two console operators:

    C1  Inlet, Amine, Dehy, Flare, Utility
    C2  Cryo, Residue compression

The alarm configuration below is the plant AS FOUND: priorities set by
the integrator's defaults (every H/L High, every HH/LL Critical), no
deadbands, no delays, equipment status configured as alarms, and no
state-based suppression. Each alarm also carries a Rationalized record,
the configuration the rationalization team agrees on later in the book.
The generator uses one or the other depending on the fixes requested.
"""
from __future__ import annotations

from ..site import AlarmDef, CascadeStep, Rationalized, Site, Upset

ROOT = "RedMesa"
AREA_CONSOLE = {
    "Inlet": "C1", "Amine": "C1", "Dehy": "C1", "Flare": "C1", "Utility": "C1",
    "Cryo": "C2", "Residue": "C2",
}

# As-found priority by alarm name: the integrator's template defaults.
AS_FOUND = {"HH": 4, "LL": 4, "H": 3, "L": 3, "Fail": 1, "Trip": 4,
            "Not Running": 2, "Flame Fail": 4, "Closed": 3, "Open": 3,
            "On Battery": 4}
# Analyzer alarms came in on the analyzer vendor's template instead.
ANALYZER = {"HH": 3, "H": 2}

_specs: dict[str, dict] = {}


def _add(area, equip, tag, alarms, units=""):
    """alarms: list of (name, setpoint, behavior, rate, rat-kwargs)."""
    for name, sp, behavior, rate, rat in alarms:
        path = f"{ROOT}/{area}/{equip}/{tag}"
        src = f"prov:default:/tag:{path}:/alm:{name}"
        _specs[src] = dict(
            tag=path, name=name, area=area, console=AREA_CONSOLE[area],
            description=f"{equip} {tag}",
            priority=ANALYZER[name] if tag.startswith("AIT") else AS_FOUND[name],
            setpoint=sp, units=units, behavior=behavior, rate=rate * 6.0,
            rat=dict(rat), )


def lvl(area, equip, tag, hh=None, h=None, l=None, ll=None, rate=0.08,
        beh=None, rat=None):
    """Level or analog alarms with the four classic limits."""
    beh = beh or {}
    rat = rat or {}
    out = []
    for name, sp, dflt in (("HH", hh, 2), ("H", h, 1), ("L", l, 1), ("LL", ll, 2)):
        if sp is None:
            continue
        r = dict(priority=dflt, deadband=abs(sp) * 0.02, on_delay=5, off_delay=10)
        r.update(rat.get(name, {}))
        out.append((name, sp, beh.get(name, "normal"),
                    rate * (0.4 if name in ("HH", "LL") else 1.0), r))
    return out


def status(name, behavior="consequence", rate=0.0, **rat):
    r = dict(priority=2)
    r.update(rat)
    return [(name, 1, behavior, rate, r)]


# ---------------------------------------------------------------- Inlet
_add("Inlet", "SC-100", "LIT-1001", lvl("Inlet", "SC-100", "LIT-1001",
     hh=90, h=75, l=20, rate=0.45, rat={"HH": {"priority": 3}}), "%")
_add("Inlet", "V-100", "LIT-1002", lvl("Inlet", "V-100", "LIT-1002",
     hh=85, h=70, l=25, ll=10, rate=0.10, beh={"L": "chatter"},
     rat={"L": {"deadband": 3.0, "on_delay": 15, "off_delay": 30}}), "%")
_add("Inlet", "V-100", "PIT-1003", lvl("Inlet", "V-100", "PIT-1003",
     hh=1150, h=1100, l=850, rate=0.06), "psig")
_add("Inlet", "Inlet", "FIT-1004", lvl("Inlet", "Inlet", "FIT-1004",
     h=230, l=120, rate=0.10), "MMSCFD")
_add("Inlet", "F-101", "PDIT-1005", lvl("Inlet", "F-101", "PDIT-1005",
     h=10, rate=0.05), "psid")
_add("Inlet", "Inlet", "TIT-1007", lvl("Inlet", "Inlet", "TIT-1007",
     h=120, l=40, rate=0.04), "degF")
_add("Inlet", "P-101A", "XA-1011", status("Fail", "normal", 0.02, priority=1))
_add("Inlet", "P-101B", "XA-1012", status("Fail", "normal", 0.02, priority=1))
_add("Inlet", "P-101B", "XA-1013", status("Not Running", "status", remove=True))
_add("Inlet", "Inlet", "XV-1006", status("Closed", "consequence", priority=3))

# ---------------------------------------------------------------- Amine
_add("Amine", "T-200", "LIT-2001", lvl("Amine", "T-200", "LIT-2001",
     hh=85, h=70, l=30, ll=15, rate=0.06), "%")
_add("Amine", "T-200", "PDIT-2002", lvl("Amine", "T-200", "PDIT-2002",
     hh=12, h=8, rate=0.05, beh={"H": "chatter"},
     rat={"H": {"deadband": 0.8, "on_delay": 20, "off_delay": 60}}), "psid")
_add("Amine", "Treated Gas", "AIT-2003", lvl("Amine", "Treated Gas", "AIT-2003",
     hh=8, h=4, rate=0.05, rat={"HH": {"priority": 3}}), "ppmv H2S")
_add("Amine", "Treated Gas", "AIT-2004", lvl("Amine", "Treated Gas", "AIT-2004",
     h=50, rate=0.03, beh={"H": "stale"}), "ppmv CO2")
_add("Amine", "V-205", "LIT-2005", lvl("Amine", "V-205", "LIT-2005",
     h=75, l=25, rate=0.05), "%")
_add("Amine", "V-205", "PIT-2006", lvl("Amine", "V-205", "PIT-2006",
     h=90, rate=0.03), "psig")
_add("Amine", "T-210", "PIT-2007", lvl("Amine", "T-210", "PIT-2007",
     h=14, rate=0.04), "psig")
_add("Amine", "T-210", "TIT-2008", lvl("Amine", "T-210", "TIT-2008",
     h=262, l=240, rate=0.06), "degF")
_add("Amine", "T-210", "LIT-2009", lvl("Amine", "T-210", "LIT-2009",
     h=75, l=25, rate=0.04), "%")
_add("Amine", "Lean Amine", "FIT-2010", lvl("Amine", "Lean Amine", "FIT-2010",
     l=300, ll=200, rate=0.03), "gpm")
_add("Amine", "Amine Cooler", "TIT-2011", lvl("Amine", "Amine Cooler", "TIT-2011",
     h=130, rate=0.9, rat={"H": {"rate": 0.3}}), "degF")
_add("Amine", "P-220A", "XA-2021", status("Fail", "normal", 0.01, priority=2))
_add("Amine", "P-220B", "XA-2022", status("Fail", "normal", 0.01, priority=2))

# ---------------------------------------------------------------- Dehy
for bed in "ABC":
    n = {"A": 1, "B": 2, "C": 3}[bed]
    _add("Dehy", f"V-300{bed}", f"PDIT-30{n}1", lvl("Dehy", f"V-300{bed}",
         f"PDIT-30{n}1", h=12, rate=0.04), "psid")
    _add("Dehy", f"V-300{bed}", f"TIT-30{n}2", lvl("Dehy", f"V-300{bed}",
         f"TIT-30{n}2", h=575, rate=0.05), "degF")
_add("Dehy", "Dry Gas", "AIT-3001", lvl("Dehy", "Dry Gas", "AIT-3001",
     hh=1.0, h=0.1, rate=0.04, beh={"H": "chatter"},
     rat={"H": {"deadband": 0.02, "on_delay": 60, "off_delay": 120},
          "HH": {"priority": 3}}), "ppmv H2O")
_add("Dehy", "H-310", "TIT-3101", lvl("Dehy", "H-310", "TIT-3101",
     hh=625, h=600, l=500, rate=0.35), "degF")
_add("Dehy", "H-310", "BSL-3102", status("Flame Fail", "normal", 0.01, priority=2))
_add("Dehy", "F-320", "PDIT-3201", lvl("Dehy", "F-320", "PDIT-3201",
     h=8, rate=0.05), "psid")
_add("Dehy", "Regen Gas", "FIT-3103", lvl("Dehy", "Regen Gas", "FIT-3103",
     l=8, rate=0.04), "MMSCFD")

# ---------------------------------------------------------------- Flare
_add("Flare", "V-600", "LIT-6001", lvl("Flare", "V-600", "LIT-6001",
     hh=60, h=40, rate=0.02, rat={"HH": {"priority": 3}}), "%")
_add("Flare", "Flare", "BSL-6002", status("Flame Fail", "normal", 0.01, priority=3))
_add("Flare", "Flare", "BSL-6003", status("Flame Fail", "fleeting", 0.0,
     priority=3, on_delay=10, off_delay=5))
_add("Flare", "Flare", "BSL-6004", status("Flame Fail", "normal", 0.01, priority=3))
_add("Flare", "Flare", "PIT-6005", lvl("Flare", "Flare", "PIT-6005",
     h=5, rate=0.03), "psig")
_add("Flare", "Flare", "FIT-6006", lvl("Flare", "Flare", "FIT-6006",
     h=2.0, rate=0.03), "MMSCFD")
_add("Flare", "Purge Gas", "FIT-6007", lvl("Flare", "Purge Gas", "FIT-6007",
     l=15, rate=0.0, beh={"L": "stale"}), "SCFH")

# ---------------------------------------------------------------- Utility
_add("Utility", "Instrument Air", "PIT-7001", lvl("Utility", "Instrument Air",
     "PIT-7001", l=90, ll=80, rate=0.03, rat={"LL": {"priority": 3}}), "psig")
_add("Utility", "Fuel Gas", "PIT-7002", lvl("Utility", "Fuel Gas", "PIT-7002",
     h=150, l=100, rate=0.4, rat={"H": {"rate": 0.1}, "L": {"rate": 0.2}}), "psig")
_add("Utility", "UPS", "XA-7003", status("On Battery", "normal", 0.005, priority=3))

# ---------------------------------------------------------------- Cryo
_add("Cryo", "E-400", "TIT-4001", lvl("Cryo", "E-400", "TIT-4001",
     h=-30, l=-60, rate=0.5, rat={"H": {"rate": 0.2}, "L": {"rate": 0.2}}), "degF")
_add("Cryo", "E-400", "PDIT-4002", lvl("Cryo", "E-400", "PDIT-4002",
     h=15, rate=0.04), "psid")
_add("Cryo", "V-410", "LIT-4101", lvl("Cryo", "V-410", "LIT-4101",
     hh=80, h=65, l=20, ll=10, rate=0.08, beh={"H": "chatter"},
     rat={"H": {"deadband": 3.0, "on_delay": 15, "off_delay": 30}}), "%")
_add("Cryo", "V-410", "PIT-4102", lvl("Cryo", "V-410", "PIT-4102",
     h=900, l=700, rate=0.05), "psig")
_add("Cryo", "EC-420", "SIT-4201", lvl("Cryo", "EC-420", "SIT-4201",
     hh=24500, h=23500, l=15000, rate=0.03), "rpm")
_add("Cryo", "EC-420", "VIT-4202", lvl("Cryo", "EC-420", "VIT-4202",
     hh=3.0, h=2.0, rate=0.02, beh={"H": "fleeting"},
     rat={"H": {"on_delay": 10, "off_delay": 5, "deadband": 0.1}}), "mils")
_add("Cryo", "EC-420", "TIT-4203", lvl("Cryo", "EC-420", "TIT-4203",
     hh=230, h=210, rate=0.03), "degF")
_add("Cryo", "EC-420", "PDIT-4204", lvl("Cryo", "EC-420", "PDIT-4204",
     l=15, ll=10, rate=0.02), "psid")
_add("Cryo", "EC-420", "PIT-4205", lvl("Cryo", "EC-420", "PIT-4205",
     l=40, ll=30, rate=0.02), "psig")
_add("Cryo", "EC-420", "XA-4207", status("Trip", "consequence", priority=3))
_add("Cryo", "EC-420", "XA-4208", status("Not Running", "consequence", remove=True))
_add("Cryo", "JT", "FV-4301", status("Open", "consequence", priority=1))
_add("Cryo", "T-430", "PIT-4301", lvl("Cryo", "T-430", "PIT-4301",
     h=400, l=320, rate=0.06), "psig")
_add("Cryo", "T-430", "LIT-4302", lvl("Cryo", "T-430", "LIT-4302",
     h=75, l=25, ll=10, rate=0.06), "%")
_add("Cryo", "T-430", "TIT-4303", lvl("Cryo", "T-430", "TIT-4303",
     h=65, l=35, rate=0.6, rat={"H": {"rate": 0.2}, "L": {"rate": 0.2}}), "degF")
_add("Cryo", "T-430", "TIT-4304", lvl("Cryo", "T-430", "TIT-4304",
     h=55, l=30, rate=0.05), "degF")
_add("Cryo", "P-440A", "XA-4411", status("Fail", "normal", 0.01, priority=2))
_add("Cryo", "P-440B", "XA-4412", status("Fail", "normal", 0.01, priority=2))
_add("Cryo", "NGL", "FIT-4401", lvl("Cryo", "NGL", "FIT-4401",
     l=150, rate=0.04), "gpm")
_add("Cryo", "Cryo Residue", "TIT-4005", lvl("Cryo", "Cryo Residue", "TIT-4005",
     l=60, rate=0.04), "degF")

# ---------------------------------------------------------------- Residue
for unit in "ABC":
    n = {"A": 1, "B": 2, "C": 3}[unit]
    eq = f"K-500{unit}"
    oos = {"LL": "stale", "L": "stale"} if unit == "C" else {}   # overhaul
    _add("Residue", eq, f"PIT-5{n}01", lvl("Residue", eq, f"PIT-5{n}01",
         l=280, ll=250, rate=0.03, beh=oos), "psig")
    beh = {"H": "chatter"} if unit == "B" else {}
    rat = {"H": {"deadband": 15, "on_delay": 15, "off_delay": 30}} if unit == "B" else {}
    _add("Residue", eq, f"PIT-5{n}02", lvl("Residue", eq, f"PIT-5{n}02",
         hh=1250, h=1200, rate=0.04, beh=beh, rat=rat), "psig")
    _add("Residue", eq, f"TIT-5{n}03", lvl("Residue", eq, f"TIT-5{n}03",
         hh=320, h=300, rate=0.05), "degF")
    _add("Residue", eq, f"VIT-5{n}04", lvl("Residue", eq, f"VIT-5{n}04",
         hh=0.8, h=0.6, rate=0.03), "in/s")
    _add("Residue", eq, f"PIT-5{n}05", lvl("Residue", eq, f"PIT-5{n}05",
         l=45, ll=35, rate=0.02, beh=oos), "psig")
    _add("Residue", eq, f"LIT-5{n}06", lvl("Residue", eq, f"LIT-5{n}06",
         hh=80, h=60, rate=0.04), "%")
    _add("Residue", eq, f"XA-5{n}07", status("Trip", "consequence", priority=3))
    _add("Residue", eq, f"XA-5{n}08", status("Not Running",
         "stale" if unit == "C" else "consequence", remove=True))
_add("Residue", "Sales", "FIT-5901", lvl("Residue", "Sales", "FIT-5901",
     l=150, rate=0.03), "MMSCFD")
_add("Residue", "Header", "PIT-5902", lvl("Residue", "Header", "PIT-5902",
     h=1150, l=950, rate=0.04), "psig")


def S(area, equip, tag, name):
    return f"prov:default:/tag:{ROOT}/{area}/{equip}/{tag}:/alm:{name}"


def C(src, lo, hi, p=1.0, suppress=True):
    return (CascadeStep(src, lo, hi, p), suppress)


# ---------------------------------------------------------------- Upsets
# Each cascade entry: (step, suppress). suppress=True marks a predictable
# consequence the team later disables by design in that plant state.
_EXPANDER = [
    C(S("Cryo", "EC-420", "XA-4208", "Not Running"), 1, 3),
    C(S("Cryo", "EC-420", "SIT-4201", "L"), 2, 8),
    C(S("Cryo", "EC-420", "PDIT-4204", "L"), 5, 20),
    C(S("Cryo", "EC-420", "PDIT-4204", "LL"), 10, 40, 0.7),
    C(S("Cryo", "JT", "FV-4301", "Open"), 3, 10, suppress=False),
    C(S("Cryo", "V-410", "LIT-4101", "H"), 20, 90),
    C(S("Cryo", "V-410", "LIT-4101", "HH"), 60, 180, 0.6, suppress=False),
    C(S("Cryo", "V-410", "PIT-4102", "H"), 10, 60),
    C(S("Cryo", "E-400", "TIT-4001", "H"), 60, 300),
    C(S("Cryo", "T-430", "PIT-4301", "H"), 20, 120),
    C(S("Cryo", "T-430", "TIT-4303", "L"), 120, 600),
    C(S("Cryo", "T-430", "TIT-4304", "L"), 120, 600),
    C(S("Cryo", "T-430", "LIT-4302", "L"), 180, 700),
    C(S("Cryo", "T-430", "LIT-4302", "LL"), 300, 900, 0.5),
    C(S("Cryo", "NGL", "FIT-4401", "L"), 200, 800),
    C(S("Cryo", "Cryo Residue", "TIT-4005", "L"), 30, 200),
    C(S("Residue", "K-500A", "PIT-5101", "L"), 30, 120),
    C(S("Residue", "K-500B", "PIT-5201", "L"), 30, 120),
    C(S("Residue", "K-500B", "PIT-5201", "LL"), 60, 240, 0.4),
    C(S("Residue", "Sales", "FIT-5901", "L"), 60, 300),
    C(S("Residue", "Header", "PIT-5902", "L"), 60, 300),
    C(S("Flare", "Flare", "FIT-6006", "H"), 10, 60, suppress=False),
    C(S("Flare", "Flare", "PIT-6005", "H"), 10, 60),
    C(S("Inlet", "V-100", "PIT-1003", "H"), 60, 240),
]

_COMPRESSOR = [
    C(S("Residue", "K-500A", "XA-5108", "Not Running"), 1, 3),
    C(S("Residue", "K-500A", "PIT-5105", "L"), 5, 20),
    C(S("Residue", "K-500A", "PIT-5105", "LL"), 10, 30),
    C(S("Residue", "Header", "PIT-5902", "L"), 20, 120, suppress=False),
    C(S("Residue", "Sales", "FIT-5901", "L"), 30, 200),
    C(S("Residue", "K-500B", "TIT-5203", "H"), 120, 600, 0.6, suppress=False),
    C(S("Cryo", "V-410", "PIT-4102", "H"), 30, 180),
    C(S("Cryo", "T-430", "PIT-4301", "H"), 30, 180),
    C(S("Flare", "Flare", "FIT-6006", "H"), 20, 120, suppress=False),
    C(S("Flare", "Flare", "PIT-6005", "H"), 20, 120),
    C(S("Inlet", "V-100", "PIT-1003", "H"), 60, 300),
    C(S("Inlet", "Inlet", "FIT-1004", "L"), 120, 400),
]

_SLUG = [
    C(S("Inlet", "SC-100", "LIT-1001", "HH"), 30, 180, 0.7, suppress=False),
    C(S("Inlet", "V-100", "LIT-1002", "H"), 20, 120),
    C(S("Inlet", "V-100", "LIT-1002", "HH"), 60, 240, 0.5, suppress=False),
    C(S("Inlet", "Inlet", "FIT-1004", "H"), 5, 60),
    C(S("Inlet", "V-100", "PIT-1003", "H"), 10, 90),
    C(S("Inlet", "F-101", "PDIT-1005", "H"), 60, 300),
    C(S("Amine", "T-200", "LIT-2001", "H"), 120, 600, 0.6),
    C(S("Amine", "T-200", "PDIT-2002", "H"), 120, 600, 0.5),
    C(S("Inlet", "P-101A", "XA-1011", "Fail"), 60, 300, 0.2, suppress=False),
]

_FOAM = [
    C(S("Amine", "T-200", "LIT-2001", "L"), 30, 200),
    C(S("Amine", "Treated Gas", "AIT-2003", "H"), 60, 400, suppress=False),
    C(S("Amine", "Treated Gas", "AIT-2003", "HH"), 200, 900, 0.5, suppress=False),
    C(S("Amine", "V-205", "LIT-2005", "H"), 60, 400),
    C(S("Amine", "Lean Amine", "FIT-2010", "L"), 60, 300, 0.6),
    C(S("Amine", "T-210", "TIT-2008", "L"), 300, 900, 0.5),
    C(S("Amine", "T-210", "LIT-2009", "L"), 200, 800, 0.6),
]

_POWER = []
for area, equip, tag, name in [
    ("Inlet", "P-101A", "XA-1011", "Fail"), ("Inlet", "P-101B", "XA-1012", "Fail"),
    ("Amine", "P-220A", "XA-2021", "Fail"), ("Amine", "P-220B", "XA-2022", "Fail"),
    ("Cryo", "P-440A", "XA-4411", "Fail"), ("Cryo", "P-440B", "XA-4412", "Fail"),
    ("Cryo", "EC-420", "XA-4207", "Trip"), ("Residue", "K-500A", "XA-5107", "Trip"),
    ("Residue", "K-500B", "XA-5207", "Trip"), ("Dehy", "H-310", "BSL-3102", "Flame Fail"),
    ("Utility", "Instrument Air", "PIT-7001", "L"), ("Inlet", "Inlet", "XV-1006", "Closed"),
]:
    _POWER.append(C(S(area, equip, tag, name), 1, 20, suppress=False))
for item in _EXPANDER + _COMPRESSOR + _FOAM:
    step, sup = item
    _POWER.append(C(step.alarm, step.min_s + 20, step.max_s + 400, 0.9, sup))
for area, equip, tag, name in [
    ("Residue", "K-500B", "XA-5208", "Not Running"), ("Residue", "K-500B", "PIT-5205", "L"),
    ("Residue", "K-500B", "PIT-5205", "LL"), ("Amine", "Lean Amine", "FIT-2010", "LL"),
    ("Dehy", "Regen Gas", "FIT-3103", "L"), ("Dehy", "H-310", "TIT-3101", "L"),
    ("Utility", "Fuel Gas", "PIT-7002", "L"), ("Inlet", "Inlet", "FIT-1004", "L"),
    ("Flare", "V-600", "LIT-6001", "H"), ("Amine", "T-210", "PIT-2007", "H"),
    ("Cryo", "EC-420", "PIT-4205", "L"), ("Cryo", "EC-420", "PIT-4205", "LL"),
]:
    _POWER.append(C(S(area, equip, tag, name), 10, 600))

UPSET_TABLE = [
    ("Expander trip", "CRYO_BYPASS", 1.2, (3, 10), S("Cryo", "EC-420", "XA-4207", "Trip"), _EXPANDER),
    ("K-500A trip", "K500A_DOWN", 1.5, (1, 6), S("Residue", "K-500A", "XA-5107", "Trip"), _COMPRESSOR),
    ("Inlet slug", "SLUG", 2.5, (0.5, 2), S("Inlet", "SC-100", "LIT-1001", "H"), _SLUG),
    ("Amine foaming", "FOAM", 1.0, (2, 8), S("Amine", "T-200", "PDIT-2002", "HH"), _FOAM),
    ("Power dip", "POWER_DIP", 0.17, (8, 16), S("Utility", "UPS", "XA-7003", "On Battery"), _POWER),
]


def build() -> Site:
    # Fold state-based suppression decisions into each alarm's record.
    suppress: dict[str, set[str]] = {}
    for _, state, _, _, _, cascade in UPSET_TABLE:
        for step, sup in cascade:
            if sup:
                suppress.setdefault(step.alarm, set()).add(state)
    alarms = []
    for src, spec in _specs.items():
        rat = dict(spec["rat"])
        rat["suppress_in"] = tuple(sorted(suppress.get(src, ())))
        alarms.append(AlarmDef(**{**spec, "rat": Rationalized(**rat)}))
    upsets = [Upset(n, st, pm, dur, ini, tuple(s for s, _ in cas))
              for n, st, pm, dur, ini, cas in UPSET_TABLE]
    known = {a.source for a in alarms}
    for u in upsets:
        for step in (u.initiator, *[c.alarm for c in u.cascade]):
            if step not in known:
                raise ValueError(f"upset {u.name} references unknown alarm {step}")
    return Site(
        name="Red Mesa Gas Plant",
        alarms=alarms,
        upsets=upsets,
        consoles={f"{ROOT}/{a}": c for a, c in AREA_CONSOLE.items()},
        operators={"C1": ("usr:dreyes", "usr:jpatel"), "C2": ("usr:nholt", "usr:mcruz")},
        signals={
            # chatter: noisy PV hovering at the setpoint
            S("Inlet", "V-100", "LIT-1002", "L"): dict(sigma=0.9, windows=0.6, minutes=(8, 30)),
            S("Amine", "T-200", "PDIT-2002", "H"): dict(sigma=0.25, windows=0.45, minutes=(10, 40)),
            S("Dehy", "Dry Gas", "AIT-3001", "H"): dict(sigma=0.008, windows=0.7, minutes=(10, 45)),
            S("Cryo", "V-410", "LIT-4101", "H"): dict(sigma=1.0, windows=0.9, minutes=(10, 40)),
            S("Residue", "K-500B", "PIT-5202", "H"): dict(sigma=5.0, windows=0.7, minutes=(8, 35)),
            # fleeting: short spikes, mean duration in seconds
            S("Cryo", "EC-420", "VIT-4202", "H"): dict(spikes=12.0, mean_s=1.5),
            S("Flare", "Flare", "BSL-6003", "Flame Fail"): dict(spikes=20.0, mean_s=0.8),
        },
        stale_periods={
            # (start day, end day) offsets from the start of the generated
            # window; the condition stands the whole span unless fixed
            S("Amine", "Treated Gas", "AIT-2004", "H"): [(0, 49.3), (60.2, 400)],
            S("Flare", "Purge Gas", "FIT-6007", "L"): [(0, 400)],
            S("Residue", "K-500C", "PIT-5305", "L"): [(11.4, 85.6)],
            S("Residue", "K-500C", "PIT-5301", "L"): [(11.5, 85.6)],
            S("Residue", "K-500C", "PIT-5301", "LL"): [(11.5, 85.6)],
            S("Dehy", "F-320", "PDIT-3201", "H"): [(20.3, 41.7), (104.8, 131.2)],
            S("Flare", "Flare", "BSL-6004", "Flame Fail"): [(33.6, 96.1)],
            S("Residue", "K-500C", "PIT-5305", "LL"): [(11.4, 85.6)],
            S("Residue", "K-500C", "XA-5308", "Not Running"): [(11.4, 85.6), (137.3, 141.5)],
            S("Inlet", "P-101B", "XA-1013", "Not Running"): [
                (0, 29.4), (31.3, 59.4), (61.5, 89.4), (91.4, 118.6),
                (120.4, 150.5), (152.4, 400)],
        },
    )
