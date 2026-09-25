# tools

`snapshot.py` extracts every block marked

```
# listing: name
...
# end listing
```

from `src/` and `tests/` into `tools/listings.json`. The book prints
listings by name from that file, so a printed listing is always the code
at the tagged commit. Run it after any change to a marked block:

```
python tools/snapshot.py
```

It fails on a duplicate name or an unclosed block.
