"""Exponential backoff for automatic reconnection."""
from __future__ import annotations

import random


class Backoff:
    def __init__(self, base: float = 1.0, factor: float = 2.0, maximum: float = 20.0,
                 jitter: float = 0.2, rng: random.Random | None = None):
        if base <= 0 or factor < 1 or maximum < base:
            raise ValueError("invalid backoff parameters")
        self.base, self.factor, self.maximum, self.jitter = base, factor, maximum, jitter
        self.attempt = 0
        self._rng = rng or random.Random()

    def next_delay(self) -> float:
        raw = min(self.maximum, self.base * (self.factor ** self.attempt))
        self.attempt += 1
        spread = raw * self.jitter
        return max(0.0, raw + self._rng.uniform(-spread, spread))

    def reset(self) -> None:
        self.attempt = 0
