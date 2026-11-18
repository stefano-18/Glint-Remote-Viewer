"""Measures the delay a platform (Twitch/YouTube) adds, using a public live stream.

For every received segment its EXT-X-PROGRAM-DATE-TIME (when the platform produced it) is
compared with the local arrival time. The Windows clock offset is corrected with a server's Date
header (1 s resolution), so the result is "estimated ±1 s". No accounts, no sign-in.

Usage: python tools/platform_latency.py URL [URL...] [--seconds 25]
"""
from __future__ import annotations

import argparse
import email.utils
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from viewer.bridge import ResolveError, open_stream  # noqa: E402
from viewer.profiles import PROFILES  # noqa: E402
from viewer.source import parse_source  # noqa: E402


def clock_offset() -> float | None:
    """server - local (s). Positive = the PC clock is behind."""
    vals = []
    for url in ("https://www.google.com", "https://www.cloudflare.com"):
        try:
            t0 = time.time()
            r = requests.head(url, timeout=5)
            t1 = time.time()
            d = email.utils.parsedate_to_datetime(r.headers["Date"]).timestamp()
            vals.append(d + 0.5 - (t0 + t1) / 2)  # +0.5: Date is truncated to the second
        except Exception:  # noqa: BLE001
            pass
    return statistics.median(vals) if vals else None


def measure(url: str, profile_key: str, seconds: float, offset: float) -> dict:
    src = parse_source(url)
    prof = PROFILES[profile_key]
    t_open = time.time()
    try:
        opened = open_stream(src, prof, "best")
    except ResolveError as err:
        return {"url": url, "profile": profile_key, "error": str(err)}
    t_first = None
    samples = []
    tr = opened.tracker
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            d = opened.adapter.read(64 * 1024)
            if not d:
                break
            now = time.time() + offset
            if t_first is None:
                t_first = time.time() - t_open
            ts = tr.time_at(opened.adapter.bytes_read) if tr else None
            if ts:
                samples.append(now - ts)
    finally:
        opened.adapter.close()
    durs = tr.avg_duration() if tr else None
    res = {"url": url, "platform": src.platform, "profile": profile_key, "quality": opened.name,
           "segment_s": round(durs, 2) if durs else None, "first_data_s": round(t_first or -1, 2)}
    if samples:
        tail = samples[len(samples) // 3:]  # skip the start-up (the live edge is downloaded in one burst)
        res.update(lag_median_s=round(statistics.median(tail), 2), lag_min_s=round(min(tail), 2),
                   lag_max_s=round(max(tail), 2))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--seconds", type=float, default=25)
    ap.add_argument("--profiles", default="ultra,balanced,stable")
    a = ap.parse_args()
    off = clock_offset()
    print(f"Clock offset (server-local): {off if off is not None else 'unknown'} s")
    for url in a.urls:
        for pk in a.profiles.split(","):
            r = measure(url, pk, a.seconds, off or 0.0)
            print(r, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
