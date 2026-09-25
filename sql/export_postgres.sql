-- Export the Ignition alarm journal tables from PostgreSQL with psql:
--   psql -d ignition -f export_postgres.sql
-- Writes alarm_events.csv and alarm_event_data.csv to the current folder.
\copy (SELECT id, eventid, source, displaypath, priority, eventtype, eventflags, to_char(eventtime, 'YYYY-MM-DD HH24:MI:SS.MS') AS eventtime FROM alarm_events WHERE eventtime >= '2026-01-01' AND eventtime < '2026-07-01' ORDER BY eventtime, id) TO 'alarm_events.csv' WITH CSV HEADER
\copy (SELECT d.id, d.propname, d.dtype, d.intvalue, d.floatvalue, d.strvalue FROM alarm_event_data d JOIN alarm_events e ON e.id = d.id WHERE e.eventtime >= '2026-01-01' AND e.eventtime < '2026-07-01' ORDER BY d.id) TO 'alarm_event_data.csv' WITH CSV HEADER
