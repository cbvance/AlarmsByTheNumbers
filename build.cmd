@echo off
rem Build every journal, report, chart, and workbook into data\ and out\.
rem Run from the repo folder. Works on a local disk or a network share.
python -m almetrics build --root "%~dp0." %*
