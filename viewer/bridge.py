"""Streamlink → mpv bridge inside the same process, with per-segment delay measurement.

Every HLS segment carries an EXT-X-PROGRAM-DATE-TIME timestamp (Twitch sends it; for Twitch
"prefetch" segments Streamlink extrapolates it). We record the byte offset where each segment
starts. Knowing how many bytes mpv has read and how many it still holds in its buffer tells us
which segment is on screen, and therefore how far behind the newest published segment we are,
without relying on the PC clock.
"""
from __future__ import annotations

import bisect
import email.utils
import logging
import re
import threading
import time
from dataclasses import dataclass, field

from streamlink import Streamlink
from streamlink.exceptions import NoPluginError, PluginError, StreamError
from streamlink.options import Options
from streamlink.plugin.plugin import stream_weight
from streamlink.stream.hls import HLSStream

from .profiles import Profile
from .source import Source

ALIASES = {"best", "worst", "best-unfiltered", "worst-unfiltered"}

OFFLINE, PRIVATE, UNAVAILABLE, NETWORK, OTHER = "offline", "private", "unavailable", "network", "other"


class ResolveError(Exception):
    """Connection error meant to be shown to the user.

    kind: offline (not live; retried), private (needs a signed-in account; not retried),
    unavailable (not playable; not retried), network / other (retried).
    """

    def __init__(self, message: str, kind: str = OTHER):
        super().__init__(message)
        self.kind = kind

    @property
    def offline(self) -> bool:
        return self.kind == OFFLINE

    @property
    def retryable(self) -> bool:
        return self.kind in (OFFLINE, NETWORK, OTHER)


_YT_INFO = re.compile(r"Could not get video info - (\w+): ?(.*)")


def classify_plugin_messages(messages: list[str]) -> ResolveError | None:
    """Turn the YouTube plugin's log messages (it raises no exception) into a clear error."""
    for msg in messages:
        m = _YT_INFO.search(msg)
        if not m:
            continue
        status, reason = m.group(1).upper(), m.group(2).lower()
        if status == "LOGIN_REQUIRED" or "private" in reason or "sign in" in reason:
            return ResolveError("This YouTube stream is PRIVATE: it can only be watched with an authorised "
                                "Google account. Press \"Open in browser\" to watch it with your own session.",
                                PRIVATE)
        if "member" in reason:
            return ResolveError("This stream is for channel members only. Open it in the browser with your account.",
                                PRIVATE)
        if "live stream recording" in reason or "will begin" in reason or "premiere" in reason \
                or "offline" in reason or status == "LIVE_STREAM_OFFLINE":
            return ResolveError("The YouTube stream hasn't started yet. Waiting…", OFFLINE)
        return ResolveError(f"YouTube does not allow playing this video ({status}). "
                            "Try opening it in the browser.", UNAVAILABLE)
    for msg in messages:
        if "protected videos" in msg:
            return ResolveError("Protected (DRM) video: it can't be played here. Open it in the browser.",
                                UNAVAILABLE)
        if "VOD content" in msg:
            return ResolveError("That is a recorded video, not a live stream. Open it in the browser.", UNAVAILABLE)
    return None


class _CaptureLogs(logging.Handler):
    """Collects Streamlink warnings emitted on THIS thread while the URL is being resolved."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.thread = threading.get_ident()
        self.messages: list[str] = []

    def emit(self, record):
        if record.thread == self.thread:
            self.messages.append(record.getMessage())


_clock = {"offset": None, "at": 0.0}


def clock_offset(session) -> float:
    """Server-minus-local clock offset (s), from Twitch's Date header. ±0.5 s resolution; cached 10 min."""
    if _clock["offset"] is not None and time.monotonic() - _clock["at"] < 600:
        return _clock["offset"]
    try:
        t0 = time.time()
        r = session.http.head("https://www.twitch.tv", timeout=4, raise_for_status=False)
        t1 = time.time()
        server = email.utils.parsedate_to_datetime(r.headers["Date"]).timestamp() + 0.5
        _clock.update(offset=server - (t0 + t1) / 2, at=time.monotonic())
    except Exception:  # noqa: BLE001 - no network or no header: no correction
        _clock.update(offset=0.0, at=time.monotonic() - 540)  # try again in 1 min
    return _clock["offset"]


class SegmentTracker:
    """Thread-safe. Maps byte offsets to each segment's timestamp."""

    def __init__(self, maxlen: int = 400):
        self._lock = threading.Lock()
        self._offsets: list[int] = []
        self._dates: list[float | None] = []
        self._durations: list[float] = []
        self._maxlen = maxlen
        self.written = 0

    def segment_start(self, date_ts: float | None, duration: float) -> None:
        with self._lock:
            if date_ts is None and self._dates and self._dates[-1] is not None:
                date_ts = self._dates[-1] + self._durations[-1]
            self._offsets.append(self.written)
            self._dates.append(date_ts)
            self._durations.append(max(0.0, float(duration or 0.0)))
            if len(self._offsets) > self._maxlen:
                cut = len(self._offsets) - self._maxlen
                del self._offsets[:cut], self._dates[:cut], self._durations[:cut]

    def add_bytes(self, n: int) -> None:
        with self._lock:
            self.written += n

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._offsets)

    def avg_duration(self) -> float | None:
        with self._lock:
            d = [x for x in self._durations[-10:] if x > 0]
        return sum(d) / len(d) if d else None

    def edge_ts(self) -> float | None:
        """End of the newest known segment (platform timestamp)."""
        with self._lock:
            for i in range(len(self._dates) - 1, -1, -1):
                if self._dates[i] is not None:
                    return self._dates[i] + self._durations[i]
        return None

    def time_at(self, byte_pos: int) -> float | None:
        """Platform timestamp corresponding to a byte offset in the stream."""
        with self._lock:
            if not self._offsets or byte_pos < self._offsets[0]:
                return None
            i = bisect.bisect_right(self._offsets, byte_pos) - 1
            date = self._dates[i]
            if date is None:
                return None
            start = self._offsets[i]
            if i + 1 < len(self._offsets):
                size = self._offsets[i + 1] - start
            elif i > 0:
                size = start - self._offsets[i - 1]  # estimate: size of the previous segment
            else:
                size = max(1, self.written - start)
            frac = min(1.0, max(0.0, (byte_pos - start) / max(1, size)))
            return date + frac * self._durations[i]


def instrument(stream: HLSStream, tracker: SegmentTracker) -> None:
    """Replace (for this instance only) the HLS writer with a subclass that reports to the tracker."""
    base_reader = stream.__reader__
    base_writer = base_reader.__writer__

    class TrackingWriter(base_writer):  # type: ignore[misc, valid-type]
        def write(self, segment, result, *data):
            is_map = bool(data and data[0])
            if not is_map and not self.should_filter_segment(segment):
                date = getattr(segment, "date", None)
                tracker.segment_start(date.timestamp() if date else None, getattr(segment, "duration", 0.0))
            return super().write(segment, result, *data)

        def _write_into_buffer(self, iterator):
            def counting(it):
                for chunk in it:
                    tracker.add_bytes(len(chunk))
                    yield chunk
            return super()._write_into_buffer(counting(iterator))

    class TrackingReader(base_reader):  # type: ignore[misc, valid-type]
        __writer__ = TrackingWriter

    stream.__reader__ = TrackingReader  # instance attribute: other sessions are unaffected


class MpvStreamAdapter:
    """Object that mpv reads through our custom stream protocol."""

    size = None  # live stream: unknown size

    def __init__(self, fd):
        self._fd = fd
        self.bytes_read = 0
        self.closed = False
        self.error: str | None = None
        self._lock = threading.Lock()

    def read(self, size: int) -> bytes:
        if self.closed:
            return b""
        try:
            data = self._fd.read(size)
        except (OSError, StreamError, ValueError) as err:  # read timeout or stream closed
            self.error = str(err) or err.__class__.__name__
            return b""
        if data:
            with self._lock:
                self.bytes_read += len(data)
        return data or b""

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self._fd.close()
        except Exception:  # noqa: BLE001 - defensive close
            pass

    cancel = close


@dataclass
class OpenedStream:
    name: str
    available: list[str]
    adapter: MpvStreamAdapter
    tracker: SegmentTracker | None
    live_edge: int
    clock_offset: float = 0.0  # server - local (s), for the "delay since ingest"
    opened_at: float = field(default_factory=time.monotonic)


def ordered_qualities(names) -> list[str]:
    real = [n for n in names if n not in ALIASES and n != "audio_only"]
    return sorted(real, key=stream_weight, reverse=True)


def pick_quality(available: list[str], wanted: str) -> str:
    """'best' → the best one; if the requested one doesn't exist, the best one not above it."""
    if not available:
        raise ResolveError("The stream offers no video quality.")
    if wanted in available:
        return wanted
    if wanted not in ("best", "worst"):
        try:
            w = stream_weight(wanted)
            for name in available:  # sorted best to worst
                if stream_weight(name) <= w:
                    return name
        except Exception:  # noqa: BLE001
            pass
    return available[-1] if wanted == "worst" else available[0]


def open_stream(source: Source, profile: Profile, quality: str, log=lambda lvl, msg: None) -> OpenedStream:
    """Blocking (network): run it off the UI thread."""
    session = Streamlink(options=dict(profile.streamlink))
    plugin_opts = None
    if source.is_twitch:
        plugin_opts = Options({"low-latency": profile.twitch_low_latency, "disable-ads": True})
    capture = _CaptureLogs()
    sl_log = logging.getLogger("streamlink")
    sl_log.addHandler(capture)
    try:
        streams = session.streams(source.url, options=plugin_opts)
    except NoPluginError:
        raise ResolveError("That address is not recognised.", UNAVAILABLE) from None
    except PluginError as err:
        log("warn", f"plugin: {err}")
        known = classify_plugin_messages([str(err)] + capture.messages)
        if known:
            raise known from None
        raise ResolveError("Could not query the stream (does the channel exist?). Retrying…") from None
    except Exception as err:  # noqa: BLE001 - requests network errors
        log("warn", f"network: {err.__class__.__name__}: {err}")
        raise ResolveError("Can't reach the platform. Check your Internet connection.", NETWORK) from None
    finally:
        sl_log.removeHandler(capture)

    for m in capture.messages:
        log("warn", f"streamlink: {m}")
    if not streams:
        known = classify_plugin_messages(capture.messages)
        if known:
            raise known
        raise ResolveError("Your friend isn't broadcasting right now. Waiting for it to start…", OFFLINE)

    available = ordered_qualities(streams.keys())
    name = pick_quality(available, quality)
    stream = streams[name]
    tracker = None
    if isinstance(stream, HLSStream):
        tracker = SegmentTracker()
        instrument(stream, tracker)
    else:
        log("info", f"non-HLS stream ({type(stream).__name__}): delay can't be measured")
    try:
        fd = stream.open()
    except StreamError as err:
        log("warn", f"open: {err}")
        raise ResolveError("Could not open the stream's video. Retrying…") from None
    offset = 0.0 if source.platform == "local" else clock_offset(session)
    log("info", f"opened {source.platform} quality={name} available={available} clock={offset:+.2f}s")
    return OpenedStream(name, available, MpvStreamAdapter(fd), tracker,
                        int(profile.streamlink.get("hls-live-edge", 3)), offset)
