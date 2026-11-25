"""A minimal FSRS-4.5 scheduler, Python standard library only.

The formulas and default weights follow the open-spaced-repetition project's
FSRS-4.5 description (https://github.com/open-spaced-repetition, MIT licence).
This is an independent re-implementation of the published equations, kept
small so the learn plugin stays dependency-free. It schedules one memory
state per concept, replayed from evidence; nothing here is stored.
"""

import math
from dataclasses import dataclass

# FSRS-4.5 default parameters.
W = [0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031,
     1.6474, 0.1367, 1.0461, 2.1072, 0.0793, 0.3246, 1.587, 0.2272, 2.8755]
DECAY = -0.5
FACTOR = 19 / 81  # makes retrievability 0.9 when elapsed days == stability

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4


def _clamp_d(d):
    return min(10.0, max(1.0, d))


def _init_d(g):
    return _clamp_d(W[4] - (g - 3) * W[5])


@dataclass
class Memory:
    stability: float
    difficulty: float
    last_review_days: float  # time of last review, in days since the epoch

    def retrievability(self, now_days):
        elapsed = max(0.0, now_days - self.last_review_days)
        return (1 + FACTOR * elapsed / self.stability) ** DECAY

    def due_days(self, desired_retention=0.9):
        """Absolute due time, in days since the epoch."""
        interval = self.stability / FACTOR * (desired_retention ** (1 / DECAY) - 1)
        return self.last_review_days + max(interval, 0.0)


def review(mem, grade, now_days):
    """Return the memory state after a review with the given grade (1-4)."""
    if grade not in (AGAIN, HARD, GOOD, EASY):
        raise ValueError(f"grade must be 1-4, got {grade}")
    if mem is None:
        return Memory(stability=W[grade - 1], difficulty=_init_d(grade), last_review_days=now_days)

    r = mem.retrievability(now_days)
    d = mem.difficulty - W[6] * (grade - 3)
    d = _clamp_d(W[7] * _init_d(GOOD) + (1 - W[7]) * d)
    s, old_d = mem.stability, mem.difficulty
    if grade == AGAIN:
        new_s = W[11] * old_d ** (-W[12]) * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))
        new_s = min(new_s, s)
    else:
        hard = W[15] if grade == HARD else 1.0
        easy = W[16] if grade == EASY else 1.0
        new_s = s * (math.exp(W[8]) * (11 - old_d) * s ** (-W[9])
                     * (math.exp(W[10] * (1 - r)) - 1) * hard * easy + 1)
    return Memory(stability=max(new_s, 0.01), difficulty=d, last_review_days=now_days)
