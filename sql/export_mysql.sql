-- Export the Ignition alarm journal tables from MySQL or MariaDB.
-- mysql -u user -p -D ignition --batch -e "source export_mysql.sql" writes
-- tab-separated output; almetrics reads CSV, so export with a client
-- that writes CSV (Workbench: Export recordset) or convert the tabs.
SET @from = '2026-01-01', @to = '2026-07-01';

SELECT id, eventid, source, displaypath, priority, eventtype, eventflags,
       DATE_FORMAT(eventtime, '%Y-%m-%d %H:%i:%s.%f') AS eventtime
FROM alarm_events
WHERE eventtime >= @from AND eventtime < @to
ORDER BY eventtime, id;

SELECT d.id, d.propname, d.dtype, d.intvalue, d.floatvalue, d.strvalue
FROM alarm_event_data d
JOIN alarm_events e ON e.id = d.id
WHERE e.eventtime >= @from AND e.eventtime < @to
ORDER BY d.id;
