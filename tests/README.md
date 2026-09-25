# tests

```
python -m pytest -q
```

| File | Covers |
|---|---|
| `conftest.py` | a builder for tiny hand-made journals with known answers |
| `test_journal.py` | SQLite and CSV round trips, timestamp shapes |
| `test_episodes.py` | episodes, ack after clear, orphans, shelving, consoles |
| `test_metrics.py` | 10-minute buckets, flood start and end rules, priority mix |
| `test_nuisance.py` | chattering, fleeting, stale and standing snapshots |
| `test_generator.py` | alarm logic, determinism, as-found is bad, fixes help |
| `test_reports.py` | bad actors, MADB workbook, shelving, compare |
| `test_cli.py` | every subcommand end to end on a five-day journal |

The generator tests build 30-day journals, so the suite takes a few
seconds rather than a fraction of one.
