"""Shared fixtures: tiny hand-built journals whose answers are known."""

from datetime import datetime, timedelta

import pytest

from almetrics.journal import ACK, ACTIVE, CLEAR, FLAG_SHELVED, Event

T0 = datetime(2026, 1, 1, 0, 0, 0)
SRC = "prov:default:/tag:RedMesa/Cryo/V-410/LIT-4101:/alm:H"
SRC2 = "prov:default:/tag:RedMesa/Inlet/V-100/LIT-1002:/alm:L"


class Builder:
    """Append transitions in any order; events() returns them sorted."""

    def __init__(self):
        self.rows = []

    def cycle(
        self, eid, src, on_s, off_s=None, ack_s=None, priority=3, shelved=False
    ):
        flags = FLAG_SHELVED if shelved else 0
        self._add(eid, src, priority, ACTIVE, flags, on_s)
        if off_s is not None:
            self._add(eid, src, priority, CLEAR, flags, off_s)
        if ack_s is not None:
            self._add(eid, src, priority, ACK, 0, ack_s)
        return self

    def _add(self, eid, src, pri, etype, flags, s):
        self.rows.append(
            Event(
                len(self.rows) + 1,
                eid,
                src,
                src.rsplit("/", 1)[-1],
                pri,
                etype,
                flags,
                T0 + timedelta(seconds=s),
            )
        )

    def events(self):
        return sorted(self.rows, key=lambda e: (e.eventtime, e.id))


@pytest.fixture
def builder():
    return Builder()
