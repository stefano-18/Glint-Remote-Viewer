"""Unit tests of the logic (no network, no mpv)."""
import json
import random

import pytest

from viewer import config as cfg
from viewer.bridge import SegmentTracker, ordered_qualities, pick_quality
from viewer.catchup import CatchupController
from viewer.diagnostics import LogBuffer, sanitize
from viewer.profiles import BALANCED, PROFILES, STABLE, ULTRA, get_profile
from viewer.reconnect import Backoff
from viewer.source import SourceError, parse_source


# ---------------------------------------------------------------- source
@pytest.mark.parametrize("text,platform,url", [
    ("MiAmigo_PS5", "twitch", "https://www.twitch.tv/miamigo_ps5"),
    ("twitch.tv/MiAmigo", "twitch", "https://www.twitch.tv/miamigo"),
    ("https://www.twitch.tv/miamigo?ref=x", "twitch", "https://www.twitch.tv/miamigo"),
    ("https://m.twitch.tv/miamigo/", "twitch", "https://www.twitch.tv/miamigo"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("https://www.youtube.com/live/dQw4w9WgXcQ?si=abc", "youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("@MiCanal", "youtube", "https://www.youtube.com/@MiCanal/live"),
    ("https://www.youtube.com/@MiCanal", "youtube", "https://www.youtube.com/@MiCanal/live"),
])
def test_parse_valid(text, platform, url):
    s = parse_source(text)
    assert (s.platform, s.url) == (platform, url)


@pytest.mark.parametrize("text", [
    "", "   ", "abc", "a b c", "x" * 400, "https://evil.example.com/twitch.tv/miamigo",
    "https://www.twitch.tv/videos/12345", "https://www.twitch.tv/miamigo/clip/xyz",
    "file:///C:/Windows/win.ini", "javascript:alert(1)", "https://www.youtube.com/watch?v=short",
    "http://127.0.0.1:8765/live.m3u8",  # local without explicit permission
    "https://www.twitch.tv/", "ftp://twitch.tv/miamigo",
])
def test_parse_invalid(text):
    with pytest.raises(SourceError):
        parse_source(text)


def test_parse_local_only_when_allowed():
    s = parse_source("http://127.0.0.1:8765/live.m3u8?x=1", allow_local=True)
    assert s.platform == "local" and s.url == "hls://http://127.0.0.1:8765/live.m3u8"
    with pytest.raises(SourceError):
        parse_source("http://192.168.1.5/live.m3u8", allow_local=True)


# --------------------------------------------------------------- profiles
def test_profiles_differ_in_real_parameters():
    assert set(PROFILES) == {"ultra", "balanced", "stable"}
    edges = [p.streamlink["hls-live-edge"] for p in (ULTRA, BALANCED, STABLE)]
    caches = [p.mpv["cache-secs"] for p in (ULTRA, BALANCED, STABLE)]
    assert edges == sorted(edges) and len(set(edges)) == 3
    assert caches == sorted(caches) and len(set(caches)) == 3
    assert STABLE.catchup.jump_above is None and STABLE.adaptive_quality
    assert get_profile("nope") is BALANCED


def test_profile_streamlink_options_exist():
    from streamlink import Streamlink
    s = Streamlink()
    for p in PROFILES.values():
        for k in p.streamlink:
            assert s.get_option(k) is not None, k
        s2 = Streamlink(options=dict(p.streamlink))
        for k, v in p.streamlink.items():
            assert s2.get_option(k) == v


# ---------------------------------------------------------------- catchup
def test_catchup_hysteresis_and_jump_cooldown():
    c = CatchupController(BALANCED.catchup)
    assert c.update(0, 0.5, 3).speed == 1.0
    assert c.update(1, 2.5, 3).speed == BALANCED.catchup.speed       # starts catching up
    assert c.update(2, 1.0, 3).speed == BALANCED.catchup.speed       # keeps going (hysteresis)
    assert c.update(3, 0.4, 3).speed == 1.0                          # caught up
    assert c.update(4, 3.0, 0.2).speed == 1.0                        # low buffer: no speed-up
    d = c.update(5, 12.0, 3)
    assert d.jump
    assert not c.update(10, 12.0, 3).jump                            # cooldown
    assert c.update(5 + BALANCED.catchup.jump_cooldown + 1, 12.0, 3).jump


def test_catchup_disabled_and_unknown():
    c = CatchupController(ULTRA.catchup, enabled=False)
    assert c.update(0, 50, 5).speed == 1.0 and not c.update(0, 50, 5).jump
    c = CatchupController(ULTRA.catchup)
    assert c.update(0, None, 5).speed == 1.0
    c = CatchupController(STABLE.catchup)
    assert not c.update(0, 100, 20).jump  # stability mode never jumps


# ---------------------------------------------------------------- backoff
def test_backoff_grows_and_caps():
    b = Backoff(base=1, maximum=20, jitter=0, rng=random.Random(1))
    assert [b.next_delay() for _ in range(7)] == [1, 2, 4, 8, 16, 20, 20]
    b.reset()
    assert b.next_delay() == 1
    with pytest.raises(ValueError):
        Backoff(base=0)


# ----------------------------------------------------------------- config
def test_config_roundtrip_and_validation(tmp_path):
    p = tmp_path / "s.json"
    s = cfg.Settings()
    for i in range(15):
        s.remember(f"canal{i:02d}")
    s.remember("canal03")
    s.volume = 55
    cfg.save(s, p)
    back = cfg.load(p)
    assert back.volume == 55 and back.history[0] == "canal03" and len(back.history) == cfg.HISTORY_MAX
    p.write_text(json.dumps({"volume": 999, "profile": "hack", "hwdec": "rm -rf", "muted": "yes",
                             "history": [1, "ok", "x" * 500], "auto_reconnect": False}))
    v = cfg.load(p)
    assert (v.volume, v.profile, v.hwdec, v.muted) == (80, "balanced", "d3d11va", False)
    assert v.history == ["ok"] and v.auto_reconnect is False
    p.write_text("{not json")
    assert cfg.load(p) == cfg.Settings()


# ------------------------------------------------------------ diagnostics
def test_sanitize_removes_secrets():
    raw = ("GET https://usher.ttvnw.net/api/channel/hls/x.m3u8?token=SECRET1&sig=SECRET2&p=1 "
           "Authorization: OAuth abcdefghijklmnop Client-Integrity: SECRET3 "
           "C:\\Users\\alice\\AppData 192.168.1.33 password=hunter2")
    out = sanitize(raw)
    for secret in ("SECRET1", "SECRET2", "SECRET3", "abcdefghijklmnop", "alice", "192.168.1.33", "hunter2"):
        assert secret not in out


def test_logbuffer_export(tmp_path):
    lb = LogBuffer(maxlen=3)
    for i in range(5):
        lb.add("error", f"e{i} token=XYZ")
    p = lb.export(tmp_path / "log.txt", "cabecera")
    txt = p.read_text(encoding="utf-8")
    assert "XYZ" not in txt and "e4" in txt and "e0" not in txt and lb.errors == 5


# ---------------------------------------------------------------- tracker
def test_segment_tracker_mapping():
    t = SegmentTracker()
    t.segment_start(1000.0, 2.0)
    t.add_bytes(1000)
    t.segment_start(None, 2.0)       # extrapolated date → 1002
    t.add_bytes(1000)
    t.segment_start(1004.0, 2.0)
    t.add_bytes(500)
    assert t.edge_ts() == 1006.0
    assert t.time_at(0) == 1000.0
    assert t.time_at(500) == pytest.approx(1001.0)
    assert t.time_at(1500) == pytest.approx(1003.0)
    assert t.time_at(2500) == pytest.approx(1005.0)  # last one: size estimated from the previous one
    assert t.avg_duration() == 2.0


def test_quality_ordering_and_pick():
    names = ["audio_only", "160p", "1080p60", "720p60", "480p", "best", "worst", "720p"]
    order = ordered_qualities(names)
    assert order[0] == "1080p60" and "best" not in order and "audio_only" not in order
    assert pick_quality(order, "best") == "1080p60"
    assert pick_quality(order, "720p60") == "720p60"
    assert pick_quality(order, "936p60") == "720p60"   # best one not above the requested one
    assert pick_quality(order, "worst") == "160p"


# ------------------------------------------------------- private youtube
def test_classify_youtube_messages():
    from viewer.bridge import OFFLINE, PRIVATE, UNAVAILABLE, classify_plugin_messages
    c = classify_plugin_messages
    assert c(["Could not get video info - LOGIN_REQUIRED: This video is private"]).kind == PRIVATE
    assert c(["Could not get video info - LOGIN_REQUIRED: Sign in to confirm your age"]).kind == PRIVATE
    assert c(["Could not get video info - UNPLAYABLE: Join this channel to get access to members-only content"]
             ).kind == PRIVATE
    assert c(["Could not get video info - LIVE_STREAM_OFFLINE: This live event will begin in 2 hours"]).kind == OFFLINE
    assert c(["Could not get video info - ERROR: Video unavailable"]).kind == UNAVAILABLE
    assert c(["This plugin does not support protected videos, try yt-dlp instead"]).kind == UNAVAILABLE
    assert c(["something unrelated"]) is None
    assert not c(["Could not get video info - LOGIN_REQUIRED: x"]).retryable
    assert c(["Could not get video info - LIVE_STREAM_OFFLINE: will begin"]).retryable


def test_web_url():
    assert parse_source("miamigo").web_url == "https://www.twitch.tv/miamigo"
    assert parse_source("http://127.0.0.1:1/x.m3u8", allow_local=True).web_url is None
