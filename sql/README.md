# sql

Queries that pull the two Ignition alarm journal tables out of a plant
database as CSV, the input `almetrics` reads when you cannot hand it the
database itself.

| File | Database |
|---|---|
| `export_sqlserver.sql` | Microsoft SQL Server |
| `export_mysql.sql` | MySQL, MariaDB |
| `export_postgres.sql` | PostgreSQL (psql `\copy`) |

Each query takes a date range. Export at least 30 days; six months is
better. Keep the column names as they are. `almetrics` matches them
case-insensitively and also accepts `display path` with a space.

The table names are Ignition's defaults, `alarm_events` and
`alarm_event_data`. A journal profile can rename them under its Advanced
settings; if yours does, edit the queries.

Then:

```
almetrics metrics alarm_events.csv --consoles consoles.csv
```
