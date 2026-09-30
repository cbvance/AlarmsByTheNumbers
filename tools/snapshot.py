"""Extract named listings from the source so the book prints what the repo runs.

Mark a block in any .py file:

    # listing: parse_journal
    ...code...
    # end listing

Then run:  python tools/snapshot.py
It writes tools/listings.json ({name: {file, start, end, code}}) and fails
if a name is used twice or a block is left open. The book build reads
listings by name from that file, never from copied text.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tools" / "listings.json"


def extract(path: Path) -> dict[str, dict]:
    found, name, buf, start = {}, None, [], 0
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if s.startswith("# listing:"):
            if name:
                raise SystemExit(f"{path}:{n}: listing {name!r} not closed")
            name, buf, start = s.split(":", 1)[1].strip(), [], n + 1
        elif s == "# end listing":
            if not name:
                raise SystemExit(f"{path}:{n}: end without start")
            found[name] = {
                "file": path.relative_to(ROOT).as_posix(),
                "start": start,
                "end": n - 1,
                "code": textwrap.dedent("\n".join(buf)).strip("\n"),
            }
            name = None
        elif name:
            buf.append(line)
    if name:
        raise SystemExit(f"{path}: listing {name!r} not closed")
    return found


def main() -> int:
    listings: dict[str, dict] = {}
    for path in sorted((ROOT / "src").rglob("*.py")) + sorted(
        (ROOT / "tests").rglob("*.py")
    ):
        for name, rec in extract(path).items():
            if name in listings:
                raise SystemExit(
                    f"duplicate listing name {name!r} in {rec['file']}"
                )
            listings[name] = rec
    OUT.write_text(json.dumps(listings, indent=1) + "\n", encoding="utf-8")
    print(f"{len(listings)} listings -> {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
