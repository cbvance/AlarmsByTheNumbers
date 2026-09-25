# sites

Site models for the generator. `redmesa.py` is the book's reference
plant: a cryogenic gas plant with inlet separation, amine, dehy, cryo,
residue compression, a flare, utilities, and two console operators.

Every alarm carries two configurations: as found (integrator defaults,
no deadbands or delays, status points configured as alarms) and
rationalized (what the team agrees on later in the book). The
generator's `--fixes` option chooses which parts of the rationalized
configuration apply:

| Fix | Changes |
|---|---|
| `deadband` | rationalized deadbands and on/off delays |
| `setpoint` | setpoints moved out of the normal operating swing |
| `priority` | rationalized priorities |
| `remove` | status points that are not alarms are deleted |
| `state` | predictable trip consequences disabled by plant state |
| `stale` | the conditions behind stale alarms are repaired |

A real plant needs no site module. The analysis commands only need a
console map (`--consoles map.csv`).
