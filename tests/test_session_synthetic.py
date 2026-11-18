"""Full session (connect, outage, automatic reconnection, disconnect) with real Streamlink and a
synthetic source. The player is replaced by a test double that consumes the stream in real time the
way mpv would; real mpv playback is verified separately (the app's benchmark mode)."""
import shutil
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from synthetic_hls import SyntheticLive  # noqa: E402

from viewer.profiles import ULTRA  # noqa: E402
from viewer.session import END_EOF, END_STOP, IDLE, PLAYING, Session  # noqa: E402
from viewer.source import parse_source  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")


class FakePlayer:
    def __init__(self):
        self._end = None
        self.adapter = None
        self.loads = 0
        self.speed = 1.0
        self._stop = threading.Event()

    def on_end(self, cb):
        self._end = cb

    def play(self, adapter, profile):
        self.stop()
        self._stop = threading.Event()
        self.adapter = adapter
        self.loads += 1
        stop = self._stop
        threading.Thread(target=self._consume, args=(adapter, stop), daemon=True).start()

    def _consume(self, adapter, stop):
        while not stop.is_set():
            if not adapter.read(32 * 1024):
                if not stop.is_set() and self._end:
                    self._end(END_EOF)
                return

    def stop(self):
        self._stop.set()
        if self.adapter:
            self.adapter.close()
            if self._end:
                self._end(END_STOP)
        self.adapter = None

    def set_speed(self, s):
        self.speed = s

    def seek_forward(self, s):
        pass

    def get(self, prop):
        return {"width": 1280, "height": 720, "estimated-vf-fps": 60.0, "container-fps": 60.0,
                "demuxer-cache-duration": 1.0, "demuxer-cache-state": {"fw-bytes": 0},
                "paused-for-cache": False, "speed": self.speed, "hwdec-current": "d3d11va"}.get(prop)


def wait_for(pred, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.1)
    return False


def test_session_reconnects_after_outage():
    live = SyntheticLive(port=0, fps=30, height=720, seg=1.0)
    events = []
    try:
        live.start_encoder()
        player = FakePlayer()
        prof = replace(ULTRA, streamlink={**ULTRA.streamlink, "stream-timeout": 4.0, "stream-segment-timeout": 2.0})
        s = Session(player, notify=lambda k, t: events.append((k, t)), log=lambda *a: None)
        s.start(parse_source(live.url, allow_local=True), prof, "best")
        assert wait_for(lambda: s.state == PLAYING, 20)
        for _ in range(6):
            st = s.tick()
            time.sleep(0.5)
        assert st.metrics["lag_edge"].kind == "estimated"
        assert "Mbit/s" in st.metrics["net_bitrate"].text
        first_connect = s.last_connect_time
        assert first_connect is not None and first_connect < 10

        live.stop_encoder()
        assert wait_for(lambda: any(k == "lost" for k, _ in events), 30), events
        live.start_encoder()
        assert wait_for(lambda: s.state == PLAYING and player.loads >= 2, 60), (s.state, events[-5:])
        t_rec = time.time()
        while time.time() - t_rec < 3:
            s.tick()
            time.sleep(0.3)
        assert s.reconnects >= 1
        print(f"initial connection {first_connect:.2f}s, reconnection {s.last_connect_time:.2f}s, "
              f"retries {s.reconnects}")

        s.stop()
        assert s.state == IDLE and player.adapter is None
    finally:
        live.close()


def test_session_without_autoreconnect_goes_idle():
    player = FakePlayer()
    events = []
    s = Session(player, notify=lambda k, t: events.append((k, t)), log=lambda *a: None, auto_reconnect=False)
    s.start(parse_source("http://127.0.0.1:9/live.m3u8", allow_local=True), ULTRA, "best")
    assert wait_for(lambda: any(k == "error" for k, _ in events), 20)
    assert s.state == IDLE
