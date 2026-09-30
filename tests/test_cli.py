from almetrics.cli import main


def test_cli_end_to_end(tmp_path, capsys):
    db = tmp_path / "j.db"
    assert (
        main(["generate", "--out", str(db), "--days", "5", "--seed", "3"]) == 0
    )
    for cmd in (
        "check",
        "parse",
        "metrics",
        "floods",
        "chatter",
        "stale",
        "badactors",
        "shelving",
    ):
        assert main([cmd, str(db), "--site", "redmesa"]) == 0
    assert (
        main(
            [
                "madb",
                str(db),
                "--site",
                "redmesa",
                "--out",
                str(tmp_path / "m.xlsx"),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "charts",
                str(db),
                "--site",
                "redmesa",
                "--outdir",
                str(tmp_path / "c"),
            ]
        )
        == 0
    )
    for name in (
        "daily_rate",
        "load_by_area",
        "inventory",
        "pareto",
        "rows_per_day",
    ):
        assert (tmp_path / "c" / f"{name}.png").exists()
    out = capsys.readouterr().out
    assert "Console" in out and "C1" in out


def test_writer_builds_in_temp_then_moves(tmp_path):
    import tempfile
    from datetime import datetime
    from pathlib import Path

    from almetrics.journal import ACTIVE, JournalWriter, load_events

    target = tmp_path / "share" / "j.db"
    w = JournalWriter(target)
    assert w.tmp.parent == Path(tempfile.gettempdir())
    assert not target.exists()
    w.add(
        "e1",
        "prov:default:/tag:A:/alm:H",
        "A H",
        3,
        ACTIVE,
        0,
        datetime(2026, 1, 1),
    )
    w.close()
    assert target.exists() and not w.tmp.exists()
    assert len(load_events(target)) == 1


def test_new_journal_clears_stale_rollback_journal(tmp_path):
    from datetime import datetime

    from almetrics.journal import ACTIVE, JournalWriter, load_events

    target = tmp_path / "j.db"
    stale = tmp_path / "j.db-journal"
    stale.write_bytes(b"left over from an interrupted build")
    w = JournalWriter(target)
    w.add(
        "e1",
        "prov:default:/tag:A:/alm:H",
        "A H",
        3,
        ACTIVE,
        0,
        datetime(2026, 1, 1),
    )
    w.close()
    assert not stale.exists()
    assert len(load_events(target)) == 1


def test_readonly_open_handles_spaces(tmp_path):
    from datetime import datetime

    from almetrics.journal import ACTIVE, JournalWriter, load_events

    target = tmp_path / "Alarm Rationalization by the Numbers" / "j.db"
    w = JournalWriter(target)
    w.add(
        "e1",
        "prov:default:/tag:A:/alm:H",
        "A H",
        3,
        ACTIVE,
        0,
        datetime(2026, 1, 1),
    )
    w.close()
    assert len(load_events(target)) == 1
