"""Session controller: connect, reconnect, catch up, adaptive quality and metrics.

It does not depend on Qt: the UI calls tick() periodically and receives notices through `notify`.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from .bridge import PRIVATE, OpenedStream, ResolveError, open_stream
from .catchup import CatchupController
from .diagnostics import ESTIMATED, MEASURED, UNKNOWN, Metric, fmt_bitrate, fmt_seconds
from .profiles import Profile
from .reconnect import Backoff
from .source import Source

END_EOF, END_STOP, END_QUIT, END_ERROR = 0, 2, 3, 4

IDLE, CONNECTING, PLAYING, WAITING = "idle", "connecting", "playing", "waiting"


@dataclass
class Stats:
    state: str = IDLE
    metrics: dict[str, Metric] = field(default_factory=dict)
    excess: float | None = None


class Session:
    def __init__(self, player, notify, log, auto_reconnect=True, catchup_enabled=True):
        self.player = player
        self.notify = notify              # notify(kind, text), callable from any thread
        self.log = log
        self.auto_reconnect = auto_reconnect
        self.catchup_enabled = catchup_enabled
        self.state = IDLE
        self.source: Source | None = None
        self.profile: Profile | None = None
        self.quality = "best"
        self.current: OpenedStream | None = None
        self.backoff = Backoff(base=1.0, maximum=20.0)
        self.catchup: CatchupController | None = None
        self._gen = 0
        self._lock = threading.RLock()
        self._timer: threading.Timer | None = None
        # metrics
        self._t_connect: float | None = None   # start of the current (re)connection
        self.last_connect_time: float | None = None
        self.reconnects = 0
        self.jumps = 0
        self._rebuffers: deque[float] = deque(maxlen=50)
        self._was_buffering = False
        self._first_frame = False
        self._rate: deque[tuple[float, int]] = deque(maxlen=40)
        player.on_end(self._on_end)

    # ------------------------------------------------------------------ API
    def start(self, source: Source, profile: Profile, quality: str) -> None:
        with self._lock:
            self.source, self.profile, self.quality = source, profile, quality
            self.backoff.reset()
            self.reconnects = 0
            self.jumps = 0
            self._rebuffers.clear()
            self._connect(reason="connect")

    def stop(self) -> None:
        with self._lock:
            self._gen += 1
            self._cancel_timer()
            self.state = IDLE
            self.current = None
            self.player.stop()
            self.player.set_speed(1.0)
        self.notify("state", "Disconnected")

    def restart(self, reason: str) -> None:
        """Reopen with the current settings (mode/quality change or jump to live)."""
        with self._lock:
            if self.source is None or self.state == IDLE:
                return
            self._connect(reason=reason)

    def set_profile(self, profile: Profile) -> None:
        with self._lock:
            self.profile = profile
            if self.state in (PLAYING, CONNECTING, WAITING):
                self._connect(reason=f"mode \"{profile.name}\"")

    def set_quality(self, quality: str) -> None:
        with self._lock:
            self.quality = quality
            if self.state in (PLAYING, CONNECTING, WAITING):
                self._connect(reason=f"quality {quality}")

    # -------------------------------------------------------------- internals
    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _connect(self, reason: str) -> None:
        self._gen += 1
        gen = self._gen
        self._cancel_timer()
        self.player.stop()
        self.current = None
        self.state = CONNECTING
        self._first_frame = False
        self._was_buffering = False
        self._rate.clear()
        if self._t_connect is None:
            self._t_connect = time.monotonic()
        self.notify("state", f"Connecting ({reason})…")
        src, prof, qual = self.source, self.profile, self.quality
        threading.Thread(target=self._connect_worker, args=(gen, src, prof, qual), daemon=True).start()

    def _connect_worker(self, gen, src, prof, qual) -> None:
        try:
            opened = open_stream(src, prof, qual, self.log)
        except ResolveError as err:
            with self._lock:
                if gen != self._gen:
                    return
                if not err.retryable:  # private / not playable: retrying is pointless
                    self.state = IDLE
                    self._t_connect = None
                    self.notify("private" if err.kind == PRIVATE else "error", str(err))
                    return
                self._schedule_retry(str(err), offline=err.offline)
            return
        except Exception as err:  # noqa: BLE001
            self.log("error", f"connect: {err.__class__.__name__}: {err}")
            with self._lock:
                if gen != self._gen:
                    return
                self._schedule_retry("Unexpected error while connecting. Retrying…")
            return
        with self._lock:
            if gen != self._gen:  # the user changed something meanwhile: discard
                opened.adapter.close()
                return
            self.current = opened
            self.catchup = CatchupController(prof.catchup, enabled=self.catchup_enabled)
            self.state = PLAYING
            self.player.play(opened.adapter, prof)
        self.notify("quality", opened.name)
        self.notify("available", ",".join(opened.available))
        self.notify("state", f"Receiving · {opened.name}")

    def _schedule_retry(self, message: str, offline: bool = False) -> None:
        if not self.auto_reconnect:
            self.state = IDLE
            self._t_connect = None
            self.notify("error", message.replace(" Retrying…", "").replace(" Waiting for it to start…", ""))
            return
        self.state = WAITING
        delay = self.backoff.next_delay()
        self.notify("waiting" if offline else "error", f"{message} (next attempt in {delay:.0f} s)")
        gen = self._gen
        self._timer = threading.Timer(delay, self._retry, args=(gen,))
        self._timer.daemon = True
        self._timer.start()

    def _retry(self, gen) -> None:
        with self._lock:
            if gen != self._gen or self.source is None:
                return
            self.reconnects += 1
            self._connect(reason="retry")

    def _on_end(self, reason) -> None:
        """mpv thread. Only react to an unexpected end (EOF or error), not to stop/replace."""
        if reason not in (END_EOF, END_ERROR):
            return
        with self._lock:
            if self.state != PLAYING or self.current is None:
                return
            err = self.current.adapter.error
            self.log("warn", f"stream ended (reason={reason}, read={err or 'EOF'})")
            self.current = None
            self._t_connect = time.monotonic()
            self.notify("lost", "Signal lost")
            if self.auto_reconnect:
                self.state = WAITING
                delay = self.backoff.next_delay() if self.reconnects else 0.3
                self._timer = threading.Timer(delay, self._retry, args=(self._gen,))
                self._timer.daemon = True
                self._timer.start()
            else:
                self.state = IDLE
                self.notify("error", "The broadcast was interrupted.")

    # ---------------------------------------------------------------- tick
    def tick(self) -> Stats:
        now = time.monotonic()
        st = Stats(state=self.state)
        cur = self.current
        m = st.metrics
        p = self.player
        if cur is None or self.state != PLAYING:
            m["connect_time"] = Metric(fmt_seconds(self.last_connect_time) if self.last_connect_time else "—",
                                       MEASURED if self.last_connect_time else UNKNOWN)
            return st

        w, h = p.get("width"), p.get("height")
        m["resolution"] = Metric(f"{w}×{h}", MEASURED) if w and h else Metric.unknown()
        cfps, ofps = p.get("container-fps"), p.get("estimated-vf-fps")
        m["fps_source"] = Metric(f"{cfps:.0f}", MEASURED) if cfps else Metric.unknown()
        m["fps_shown"] = Metric(f"{ofps:.1f}", MEASURED) if ofps else Metric.unknown()
        drops = (p.get("frame-drop-count") or 0) + (p.get("decoder-frame-drop-count") or 0)
        m["dropped"] = Metric(str(drops), MEASURED) if (w and h) else Metric.unknown()
        hw = p.get("hwdec-current")
        m["hwdec"] = Metric("GPU (" + hw + ")" if hw and hw != "no" else "CPU (software)", MEASURED) \
            if (w and h) else Metric.unknown()
        vbr = p.get("video-bitrate")
        m["video_bitrate"] = Metric(fmt_bitrate(vbr), MEASURED) if vbr else Metric.unknown()

        written = cur.tracker.written if cur.tracker else cur.adapter.bytes_read
        self._rate.append((now, written))
        if len(self._rate) >= 4 and self._rate[-1][0] - self._rate[0][0] > 1.5:
            dt = self._rate[-1][0] - self._rate[0][0]
            bps = (self._rate[-1][1] - self._rate[0][1]) * 8 / dt
            m["net_bitrate"] = Metric(fmt_bitrate(bps), MEASURED)
        else:
            m["net_bitrate"] = Metric.unknown()

        buffered = p.get("demuxer-cache-duration")
        m["buffer"] = Metric(fmt_seconds(buffered), MEASURED) if buffered is not None else Metric.unknown()

        buffering = bool(p.get("paused-for-cache"))
        if buffering and not self._was_buffering and self._first_frame:
            self._rebuffers.append(now)
        self._was_buffering = buffering
        recent = sum(1 for t in self._rebuffers if now - t < 120)
        m["stalls"] = Metric(f"{recent} (last 2 min)", MEASURED)

        if not self._first_frame and w and h and (ofps or 0) > 0:
            self._first_frame = True
            if self._t_connect is not None:
                self.last_connect_time = now - self._t_connect
                self._t_connect = None
            self.backoff.reset()
        m["connect_time"] = Metric(fmt_seconds(self.last_connect_time), MEASURED) \
            if self.last_connect_time is not None else Metric.unknown()

        # Per-segment delay (estimated).
        excess = None
        lag_edge = ingest = None
        if cur.tracker is not None and cur.tracker.count:
            state = p.get("demuxer-cache-state") or {}
            fw = state.get("fw-bytes") if isinstance(state, dict) else None
            if fw is not None:
                pos = max(0, cur.adapter.bytes_read - int(fw))
                play_ts = cur.tracker.time_at(pos)
                edge = cur.tracker.edge_ts()
                if play_ts is not None and edge is not None:
                    lag_edge = max(0.0, edge - play_ts)
                    ingest = time.time() + cur.clock_offset - play_ts
                    avg = cur.tracker.avg_duration() or 2.0
                    excess = lag_edge - cur.live_edge * avg
        m["lag_edge"] = Metric(fmt_seconds(lag_edge), ESTIMATED) if lag_edge is not None else Metric.unknown()
        if ingest is not None and -5 < ingest < 120:
            # the clock is corrected with ±0.5 s resolution: anything below that cannot be refined
            m["lag_ingest"] = Metric("< 0.5 s" if ingest < 0.5 else fmt_seconds(ingest), ESTIMATED)
        else:
            m["lag_ingest"] = Metric.unknown()
        st.excess = excess

        # Catch-up.
        if self.catchup is not None and self._first_frame:
            d = self.catchup.update(now, excess, buffered)
            if d.jump:
                self.jumps += 1
                if buffered is not None and excess is not None and buffered - 0.5 > excess:
                    p.seek_forward(excess)
                    self.log("info", f"jump inside buffer +{excess:.1f}s")
                else:
                    self.log("info", "jump to live (reopen)")
                    self.restart("jump to live")
                    return st
            else:
                p.set_speed(d.speed)
            m["catchup"] = Metric(f"{d.reason} · {p.get('speed') or 1.0:.2f}×", MEASURED)

        # Adaptive quality (stability mode).
        if self.profile and self.profile.adaptive_quality and recent >= 3 and cur.available:
            try:
                idx = cur.available.index(cur.name)
            except ValueError:
                idx = -1
            if 0 <= idx < len(cur.available) - 1:
                lower = cur.available[idx + 1]
                self._rebuffers.clear()
                self.notify("info", f"Unstable connection: lowering quality to {lower}")
                self.quality = lower
                self.restart(f"quality {lower}")
        return st
