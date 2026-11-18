"""libmpv wrapper: low-latency options, D3D11VA decoding and metric reads."""
from __future__ import annotations

import ctypes
import os
import threading

from .paths import prepare_mpv_dll
from .profiles import Profile

prepare_mpv_dll()
import mpv  # noqa: E402  (needs the DLL on the PATH)

PROTOCOL = "glintremote"

# Fixed options, chosen for the lowest CPU/GPU cost on D3D11 hardware (zero-copy).
BASE_OPTIONS = dict(
    vo="gpu-next",
    gpu_api="d3d11",
    video_sync="audio",          # audio is the clock: no extra video resampling
    interpolation="no",          # no artificial frame interpolation
    keep_open="no",
    idle="yes",
    force_window="yes",
    osc="no",
    osd_level=1,
    input_default_bindings="no",
    input_vo_keyboard="yes",
    ytdl="no",
    config="no",
    load_scripts="no",
    cursor_autohide=1500,
    cache="yes",
    demuxer_seekable_cache="yes",
    hr_seek="no",
    hwdec_codecs="h264,hevc,av1,vp9",
    audio_pitch_correction="yes",  # scaletempo2 when speeding up
)


class Player:
    def __init__(self, wid: int, hwdec: str, log=lambda lvl, msg: None):
        self._log = log
        self._lock = threading.Lock()
        self._adapter = None
        self.m = mpv.MPV(wid=str(int(wid)), hwdec=hwdec, log_handler=self._on_log,
                         loglevel=os.environ.get("GLINTREMOTE_MPV_LOG", "warn"), **BASE_OPTIONS)
        self._register_stream_protocol()
        self._end_cb = None

        @self.m.event_callback("end-file")
        def _on_end(event):  # mpv event thread
            try:
                reason = event.data.reason if hasattr(event, "data") else None
            except Exception:  # noqa: BLE001
                reason = None
            if self._end_cb:
                self._end_cb(reason)

    # -- integration -------------------------------------------------------
    def _on_log(self, level, prefix, text):
        self._log(level, f"mpv/{prefix}: {text.strip()}")

    def _register_stream_protocol(self) -> None:
        """Our own protocol on top of mpv_stream_cb.

        We don't use MPV.register_stream_protocol: it copies data byte by byte in a Python loop
        (hundreds of thousands of iterations per second at 1080p60), which spikes the CPU and starves
        mpv of data. Here every block is copied with a single memmove.
        """
        keep = self._callbacks = []

        @mpv.StreamOpenFn
        def open_backend(_userdata, _uri, cb_info):
            with self._lock:
                adapter = self._adapter
            if adapter is None:
                return mpv.ErrorCode.LOADING_FAILED

            @mpv.StreamReadFn
            def read(_u, buf, size):
                try:
                    data = adapter.read(size)
                except Exception:  # noqa: BLE001 - never propagate into C
                    return -1
                n = len(data)
                if n:
                    ctypes.memmove(buf, data, n)
                return n

            @mpv.StreamCloseFn
            def close(_u):
                adapter.close()

            @mpv.StreamCancelFn
            def cancel(_u):
                adapter.cancel()

            info = cb_info.contents
            info.cookie = None
            info.read, info.close, info.cancel = read, close, cancel
            keep.append((read, close, cancel))  # keep the GC from freeing callbacks in use
            del keep[:-4]
            return 0

        self._open_backend = open_backend
        mpv._mpv_stream_cb_add_ro(self.m.handle, PROTOCOL.encode(), ctypes.c_void_p(), open_backend)

    def on_end(self, cb) -> None:
        self._end_cb = cb

    # -- control -----------------------------------------------------------
    def apply_profile(self, profile: Profile) -> None:
        for k, v in profile.mpv.items():
            try:
                self.m[k] = v
            except Exception as err:  # noqa: BLE001
                self._log("warn", f"option {k} not applied: {err}")

    def play(self, adapter, profile: Profile) -> None:
        self.apply_profile(profile)
        with self._lock:
            self._adapter = adapter
        self.m.speed = 1.0
        self.m.loadfile(f"{PROTOCOL}://live", "replace")

    def stop(self) -> None:
        with self._lock:
            adapter, self._adapter = self._adapter, None
        try:
            self.m.command("stop")
        except Exception:  # noqa: BLE001
            pass
        if adapter is not None:
            adapter.close()

    def set_volume(self, v: int) -> None:
        self.m.volume = max(0, min(130, int(v)))

    def set_mute(self, muted: bool) -> None:
        self.m.mute = bool(muted)

    def set_speed(self, s: float) -> None:
        if abs((self.get("speed") or 1.0) - s) > 1e-3:
            self.m.speed = s

    def set_hwdec(self, hw: str) -> None:
        self.m.hwdec = hw

    def seek_forward(self, seconds: float) -> None:
        self.m.command("seek", f"{seconds:.2f}", "relative")

    def audio_devices(self) -> list[tuple[str, str]]:
        try:
            return [(d["name"], d.get("description") or d["name"]) for d in (self.m.audio_device_list or [])]
        except Exception:  # noqa: BLE001
            return [("auto", "System default")]

    def set_audio_device(self, name: str) -> None:
        self.m.audio_device = name

    def get(self, prop: str):
        """Read an mpv *property* (note: MPV[...] reads options, not properties)."""
        try:
            return self.m._get_property(prop, mpv.lazy_decoder)
        except Exception:  # noqa: BLE001 - property not available yet
            return None

    def terminate(self) -> None:
        self.stop()
        try:
            self.m.terminate()
        except Exception:  # noqa: BLE001
            pass
