"""Recovery of accumulated delay relative to the live edge available on the platform.

Rule: continuous playback beats shaving off a few tenths of a second. First speed up gently
(audio stays in sync with unchanged pitch thanks to scaletempo2); jump to live only when the
delay is large, and never twice within a short time.
"""
from __future__ import annotations

from dataclasses import dataclass

from .profiles import CatchupParams


@dataclass(frozen=True)
class Decision:
    speed: float
    jump: bool = False
    reason: str = ""


class CatchupController:
    def __init__(self, params: CatchupParams | None, enabled: bool = True):
        self.params = params
        self.enabled = enabled and params is not None
        self.speeding = False
        self.last_jump: float | None = None

    def reset(self) -> None:
        self.speeding = False

    def update(self, now: float, excess: float | None, buffered: float | None) -> Decision:
        """excess: seconds of delay above the expected baseline (None = unknown).
        buffered: seconds in mpv's buffer (None = unknown)."""
        p = self.params
        if not self.enabled or p is None or excess is None:
            self.speeding = False
            return Decision(1.0, reason="no data" if excess is None else "off")

        if p.jump_above is not None and excess > p.jump_above:
            if self.last_jump is None or now - self.last_jump >= p.jump_cooldown:
                self.last_jump = now
                self.speeding = False
                return Decision(1.0, jump=True, reason=f"delay +{excess:.1f}s: jump to live")

        if buffered is not None and buffered < p.min_buffer:
            self.speeding = False
            return Decision(1.0, reason="low buffer")

        if self.speeding:
            if excess < p.release_below:
                self.speeding = False
                return Decision(1.0, reason="caught up")
            return Decision(p.speed, reason="catching up")
        if excess > p.speed_above:
            self.speeding = True
            return Decision(p.speed, reason="catching up")
        return Decision(1.0, reason="live")
