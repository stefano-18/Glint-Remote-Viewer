"""Real Streamlink integration against a local synthetic HLS source (no mpv).

Checks: opening, byte flow, per-segment timestamps, measurable delay and behaviour when the
sender goes down. Requires ffmpeg on the PATH.
"""
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from synthetic_hls import SyntheticLive  # noqa: E402

from viewer.bridge import ResolveError, open_stream  # noqa: E402
from viewer.profiles import BALANCED, ULTRA  # noqa: E402
from viewer.source import parse_source  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")


@pytest.fixture(scope="module")
def live():
    lv = SyntheticLive(port=0, fps=60, height=720, seg=1.0)
    lv.start_encoder()
    yield lv
    lv.close()


def read_for(adapter, seconds):
    t0, n = time.time(), 0
    while time.time() - t0 < seconds:
        d = adapter.read(64 * 1024)
        if not d:
            break
        n += len(d)
    return n


@pytest.mark.parametrize("profile", [ULTRA, BALANCED], ids=lambda p: p.key)
def test_open_read_and_latency(live, profile):
    src = parse_source(live.url, allow_local=True)
    opened = open_stream(src, profile, "best")
    try:
        n = read_for(opened.adapter, 6)
        assert n > 500_000, "no data arriving"
        tr = opened.tracker
        assert tr is not None and tr.count >= 3
        play_ts = tr.time_at(opened.adapter.bytes_read)
        assert play_ts is not None
        lag = time.time() - play_ts  # same clock (local ffmpeg): measured
        # With -re and 1 s segments the delay after ingest must be small and positive.
        assert -1.0 < lag < 6.0, lag
        bps = n * 8 / 6
        print(f"[{profile.key}] read {n/1e6:.1f} MB, ~{bps/1e6:.1f} Mbit/s, read delay~{lag:.2f}s")
    finally:
        opened.adapter.close()


def test_outage_ends_stream_then_recovers(live):
    prof = replace(ULTRA, streamlink={**ULTRA.streamlink, "stream-timeout": 4.0, "stream-segment-timeout": 2.0})
    src = parse_source(live.url, allow_local=True)
    opened = open_stream(src, prof, "best")
    read_for(opened.adapter, 2)
    live.stop_encoder()
    t0 = time.time()
    while opened.adapter.read(64 * 1024):
        if time.time() - t0 > 30:
            pytest.fail("the stream did not end after the sender went down")
    assert time.time() - t0 < 30
    opened.adapter.close()
    live.start_encoder()
    again = open_stream(src, prof, "best")
    try:
        assert read_for(again.adapter, 3) > 100_000
    finally:
        again.adapter.close()


def test_offline_source_reports_error():
    src = parse_source("http://127.0.0.1:9/live.m3u8", allow_local=True)
    with pytest.raises(ResolveError):
        open_stream(src, BALANCED, "best")
