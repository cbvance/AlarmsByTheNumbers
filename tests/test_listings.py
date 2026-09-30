"""Printed listings must fit the book's code block without wrapping."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_listing_fits_79_columns():
    spec = importlib.util.spec_from_file_location(
        "snapshot", ROOT / "tools" / "snapshot.py"
    )
    snap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snap)
    for path in list((ROOT / "src").rglob("*.py")) + list(
        (ROOT / "tests").rglob("*.py")
    ):
        for name, rec in snap.extract(path).items():
            longest = max(len(line) for line in rec["code"].splitlines())
            assert (
                longest <= 79
            ), f"{name} in {rec['file']} has a {longest}-column line"
