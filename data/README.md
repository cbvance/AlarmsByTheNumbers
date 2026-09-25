# data

Generated journals land here. The folder is kept in the repo; the `.db`
files are not (they are rebuilt in seconds and run to tens of megabytes).

```
almetrics generate --out data/redmesa_before.db
almetrics generate --out data/redmesa_after.db --start 2026-08-01 --days 91 --fixes all
```

Both are SQLite files holding `alarm_events` and `alarm_event_data` in
the Ignition 8.1 layout. Open them with any SQLite browser, or dump them
to CSV with `almetrics export-csv data/redmesa_before.db data/csv`.

The default seed (1843) gives the numbers printed in the book. Another
seed gives a different six months with the same planted problems.
