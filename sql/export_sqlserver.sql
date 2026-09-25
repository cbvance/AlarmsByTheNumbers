-- Export the Ignition alarm journal tables from SQL Server for almetrics.
-- Default table names; change them if the journal profile's Advanced
-- settings rename them. Run each SELECT in SSMS and use
-- "Save Results As" to CSV, or use bcp / Invoke-Sqlcmd.
DECLARE @from datetime = '2026-01-01', @to datetime = '2026-07-01';

SELECT id, eventid, source, displaypath, priority, eventtype, eventflags,
       CONVERT(varchar(23), eventtime, 121) AS eventtime
FROM alarm_events
WHERE eventtime >= @from AND eventtime < @to
ORDER BY eventtime, id;

SELECT d.id, d.propname, d.dtype, d.intvalue, d.floatvalue, d.strvalue
FROM alarm_event_data d
JOIN alarm_events e ON e.id = d.id
WHERE e.eventtime >= @from AND e.eventtime < @to
ORDER BY d.id;
