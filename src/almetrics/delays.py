"""What on-delays and off-delays would do, from the journal alone.

A journal holds when each activation began and ended. That is enough to
replay any on-delay and off-delay exactly: an on-delay drops every
activation shorter than it, and an off-delay joins activations that
re-alarm within it after a clear. A deadband needs the process value,
which the journal does not hold; that comes from the historian.
"""

from __future__ import annotations

from .episodes import Episode


# listing: replay_delays
def replay_delays(
    episodes: list[Episode], on_s: float, off_s: float, data_end
) -> int:
    """How many activations one alarm would have produced with these
    delays. Episodes must be one alarm's, in any order."""
    eps = sorted(episodes, key=lambda e: e.active)
    count = 0
    open_until = None  # when the last counted alarm would clear
    for e in eps:
        start = e.active.timestamp()
        end = (e.clear or data_end).timestamp()
        if open_until is not None and start <= open_until:
            # the condition returned while the off-delay held the alarm
            # active, so the alarm never cleared
            open_until = max(open_until, end + off_s)
            continue
        if end - start < on_s:
            continue  # cleared before the on-delay ran out
        count += 1
        open_until = end + off_s
    return count


def delay_table(
    episodes, data_end, on=(0, 5, 10, 15, 30, 60), off=(0, 10, 30, 60)
) -> list[list[int]]:
    """Activations for every on-delay (rows) and off-delay (columns)."""
    return [[replay_delays(episodes, a, b, data_end) for b in off] for a in on]


# end listing
