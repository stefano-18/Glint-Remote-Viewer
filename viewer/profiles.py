"""The three playback modes. Each one changes real Streamlink and mpv parameters.

The values are the measured starting point documented in TEST_RESULTS.md; if a setting causes
stalls, change it here (the single place where they live).
"""
from __future__ import annotations

from dataclasses import dataclass, field

MiB = 1024 * 1024


@dataclass(frozen=True)
class CatchupParams:
    # "excess" = delay behind the newest known segment minus the expected baseline delay
    speed_above: float      # speed up when the excess exceeds this (s)
    release_below: float    # back to 1.0x when it drops below this (s)
    speed: float            # catch-up speed (scaletempo2 keeps the pitch)
    jump_above: float | None  # jump to live when the excess exceeds this (None = never)
    jump_cooldown: float    # minimum seconds between jumps
    min_buffer: float       # never speed up when mpv's buffer is below this (avoids stalls)


@dataclass(frozen=True)
class Profile:
    key: str
    name: str
    description: str
    streamlink: dict = field(default_factory=dict)
    twitch_low_latency: bool = True
    mpv: dict = field(default_factory=dict)
    catchup: CatchupParams | None = None
    adaptive_quality: bool = False  # lower the quality after repeated buffering stalls


ULTRA = Profile(
    key="ultra",
    name="Ultra low latency",
    description="As close to live as possible. Minimal buffer; may stutter if the network hiccups.",
    streamlink={
        "hls-live-edge": 2,
        "hls-segment-stream-data": True,
        "stream-segment-threads": 2,
        "stream-segment-attempts": 3,
        "stream-segment-timeout": 5.0,
        "stream-timeout": 20.0,
        "ringbuffer-size": 8 * MiB,
    },
    twitch_low_latency=True,
    mpv={
        "cache-secs": 2,
        "demuxer-readahead-secs": 1,
        "cache-pause-initial": "no",
        "cache-pause-wait": 0.5,
        "audio-buffer": 0.1,
        "demuxer-max-bytes": "32MiB",
        "demuxer-max-back-bytes": "4MiB",
    },
    catchup=CatchupParams(speed_above=1.0, release_below=0.3, speed=1.06,
                          jump_above=5.0, jump_cooldown=30.0, min_buffer=0.4),
)

BALANCED = Profile(
    key="balanced",
    name="Balanced (recommended)",
    description="Smooth, good quality and little delay. Automatically recovers accumulated delay.",
    streamlink={
        "hls-live-edge": 3,
        "hls-segment-stream-data": True,
        "stream-segment-threads": 2,
        "stream-segment-attempts": 4,
        "stream-segment-timeout": 8.0,
        "stream-timeout": 30.0,
        "ringbuffer-size": 16 * MiB,
    },
    twitch_low_latency=True,
    mpv={
        "cache-secs": 4,
        "demuxer-readahead-secs": 2,
        "cache-pause-initial": "no",
        "cache-pause-wait": 1.0,
        "audio-buffer": 0.2,
        "demuxer-max-bytes": "64MiB",
        "demuxer-max-back-bytes": "8MiB",
    },
    catchup=CatchupParams(speed_above=2.0, release_below=0.5, speed=1.04,
                          jump_above=10.0, jump_cooldown=60.0, min_buffer=0.8),
)

STABLE = Profile(
    key="stable",
    name="Maximum stability",
    description="Large buffer for unreliable connections. More delay, almost no stalls or jumps.",
    streamlink={
        "hls-live-edge": 4,
        "hls-segment-stream-data": False,
        "stream-segment-threads": 2,
        "stream-segment-attempts": 6,
        "stream-segment-timeout": 15.0,
        "stream-timeout": 60.0,
        "ringbuffer-size": 32 * MiB,
    },
    twitch_low_latency=False,
    mpv={
        "cache-secs": 12,
        "demuxer-readahead-secs": 6,
        "cache-pause-initial": "yes",
        "cache-pause-wait": 3.0,
        "audio-buffer": 0.3,
        "demuxer-max-bytes": "128MiB",
        "demuxer-max-back-bytes": "8MiB",
    },
    catchup=CatchupParams(speed_above=8.0, release_below=2.0, speed=1.03,
                          jump_above=None, jump_cooldown=0.0, min_buffer=3.0),
    adaptive_quality=True,
)

PROFILES: dict[str, Profile] = {p.key: p for p in (ULTRA, BALANCED, STABLE)}
DEFAULT_PROFILE = BALANCED.key


def get_profile(key: str) -> Profile:
    return PROFILES.get(key, PROFILES[DEFAULT_PROFILE])
