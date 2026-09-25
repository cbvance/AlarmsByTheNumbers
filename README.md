# Alarms by the Numbers

Companion code for *Alarm Rationalization by the Numbers: ISA-18.2
Metrics, Bad Actors, and the Python Tools to Find Them* by Charles Vance
(LearnSCADA, 2026).

`almetrics` measures an Ignition alarm journal before you fix it. It
rebuilds alarm episodes from the `alarm_events` table, computes the
benchmark metrics used in ISA-18.2 and EEMUA 191 work, finds floods,
chattering, fleeting, stale and standing alarms, ranks the bad actors,
exports a master alarm database workbook for rationalization meetings,
and proves the result with a before-and-after report.

The book's printed listings come from tag `v1.0-book`.

## Install and run (Windows, Python 3.14)

```
py -3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[test]
python -m pytest -q
almetrics generate --out data\redmesa_before.db
almetrics metrics data\redmesa_before.db --site redmesa
```

## Network drives

The repo can live on a network share or mapped drive. Journals are built
in the local temp folder and moved into place, and analysis opens them
read-only without SQLite locking, so nothing stalls on SMB. Keep the
virtual environment on a local disk:

```
py -3.14 -m venv C:\Users\%USERNAME%\venvs\alarms
C:\Users\%USERNAME%\venvs\alarms\Scripts\activate
```

## Build everything

```
build.cmd
```

or `python -m almetrics build`. It writes both Red Mesa journals to
`data\` and every report the book prints to `out\`: metrics, floods,
chatter, stale, bad actors, shelving, the MADB workbook, the charts, and
the before-and-after comparison. Journals are built in the local temp
folder and moved into place, so the repo can live on a network share.

## Commands

| Command | Output |
|---|---|
| `generate` | synthetic Red Mesa journal in the Ignition 8.1 table layout |
| `parse` | episode, shelved, orphan, and toggle counts |
| `metrics` | rates, peaks, flood time, top-ten share, priority mix per console |
| `floods` | largest floods, first-out alarms, recurring floods |
| `chatter` | chattering and fleeting alarms |
| `stale` | stale and standing alarms by day |
| `badactors` | top-ten report, optional Pareto chart |
| `shelving` | shelved activations and disabled spans |
| `madb` | MADB workbook (.xlsx) |
| `compare` | before and after, optional chart |
| `charts` | standard chart set |
| `export-csv` | both journal tables to CSV |
| `build` | all of the above for Red Mesa, into `data` and `out` |

## Your own plant

Export the two tables with a query from `sql/`, write a console map (see
`consoles.example.csv`), and point any command at the CSV:

```
almetrics metrics alarm_events.csv --consoles consoles.csv
```

## Layout

```
src/almetrics/        the package
src/almetrics/sites/  the Red Mesa site model
tests/                pytest suite
tools/                snapshot.py: listings for the book
sql/                  export queries for SQL Server, MySQL, PostgreSQL
data/                 generated journals (not committed)
```

MIT license. Not affiliated with or endorsed by Inductive Automation,
ISA, IEC, or EEMUA.
