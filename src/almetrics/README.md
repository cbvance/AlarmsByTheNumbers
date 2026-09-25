# almetrics

| Module | Job | Book |
|---|---|---|
| `journal.py` | read and write the Ignition 8.1 tables; SQLite or CSV | Ch 6, 7 |
| `site.py` | alarm definitions, upsets, console map | Ch 5, 8 |
| `generator.py` | synthetic journal from modeled process conditions | Ch 8 |
| `episodes.py` | transition rows to alarm episodes | Ch 9 |
| `metrics.py` | rates, peaks, flood time, priority mix, top ten | Ch 10 |
| `floods.py` | flood periods, first-out, recurring floods | Ch 11 |
| `nuisance.py` | chattering, fleeting, stale, standing | Ch 12, 13 |
| `badactors.py` | top-ten report with a first-guess diagnosis | Ch 14 |
| `shelving.py` | shelved activations, disabled spans | Ch 15 |
| `madb.py` | MADB workbook for rationalization meetings | Ch 16, 17 |
| `compare.py` | before and after | Ch 20 |
| `charts.py` | grayscale charts at 4.25 in | throughout |
| `cli.py` | the `almetrics` command | throughout |

Standard library first: `sqlite3`, `csv`, `statistics`, `dataclasses`.
`openpyxl` writes the workbook and `matplotlib` draws the charts.
