"""Reproducible synthetic source: a local live HLS stream with test video, an audio tone and a clock.

It mimics what Twitch/YouTube deliver (HLS with EXT-X-PROGRAM-DATE-TIME) but on 127.0.0.1,
to genuinely test the Streamlink → mpv path, reconnection and metrics.
IMPORTANT: a test with this source does NOT prove that a real PS5 can broadcast.

Usage:
    python tools/synthetic_hls.py --port 8765 [--fps 60] [--height 1080] [--seconds 0]
URL for the app (with "Allow local test sources" enabled):
    http://127.0.0.1:8765/live.m3u8
"""
from __future__ import annotations

import argparse
import functools
import http.server
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def has_encoder(name: str) -> bool:
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return f" {name} " in out.stdout


def nvenc_works() -> bool:
    if not has_encoder("h264_nvenc"):
        return False
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=320x240:rate=30", "-frames:v", "5", "-c:v", "h264_nvenc",
                        "-f", "null", "-"], capture_output=True, timeout=30)
    return r.returncode == 0


def ffmpeg_cmd(out_dir: Path, fps: int, height: int, seg: float, nvenc: bool) -> list[str]:
    width = height * 16 // 9
    font = "C\\:/Windows/Fonts/consola.ttf"
    vf = (f"drawtext=fontfile='{font}':text='%{{localtime\\:%H\\\\\\:%M\\\\\\:%S}}.%{{eif\\:mod(n\\,{fps})\\:d\\:2}}"
          f"  f%{{n}}':x=40:y=40:fontsize={height // 14}:fontcolor=white:box=1:boxcolor=black@0.6")
    gop = int(fps * seg)
    venc = (["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "ll", "-rc", "cbr", "-b:v", "6M"]
            if nvenc else ["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-b:v", "6M"])
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-re",
        "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate={fps}",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:beep_factor=4",
        "-vf", vf, *venc, "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ac", "2",
        "-f", "hls", "-hls_time", str(seg), "-hls_list_size", "6",
        "-hls_flags", "delete_segments+program_date_time+independent_segments+omit_endlist",
        "-hls_segment_filename", str(out_dir / "seg_%05d.ts"), str(out_dir / "live.m3u8"),
    ]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


class SyntheticLive:
    """Usable from tests: start_encoder() / stop_encoder() / close()."""

    def __init__(self, port: int = 0, fps: int = 60, height: int = 1080, seg: float = 1.0, nvenc: bool | None = None):
        self.dir = Path(tempfile.mkdtemp(prefix="glintremote-hls-"))
        self.fps, self.height, self.seg = fps, height, seg
        self.nvenc = nvenc_works() if nvenc is None else nvenc
        handler = functools.partial(QuietHandler, directory=str(self.dir))
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.port = self.httpd.server_address[1]
        self.proc: subprocess.Popen | None = None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/live.m3u8"

    def start_encoder(self, wait: bool = True) -> None:
        for f in self.dir.glob("*"):
            f.unlink(missing_ok=True)
        self.proc = subprocess.Popen(ffmpeg_cmd(self.dir, self.fps, self.height, self.seg, self.nvenc),
                                     stdin=subprocess.DEVNULL)
        if wait:
            deadline = time.time() + 20
            while time.time() < deadline:
                pl = self.dir / "live.m3u8"
                if pl.exists() and pl.read_text(errors="ignore").count("#EXTINF") >= 3:
                    return
                if self.proc.poll() is not None:
                    raise RuntimeError("ffmpeg exited while starting")
                time.sleep(0.2)
            raise RuntimeError("the synthetic source did not produce segments in time")

    def stop_encoder(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def close(self) -> None:
        self.stop_encoder()
        self.httpd.shutdown()
        shutil.rmtree(self.dir, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--segment", type=float, default=1.0)
    ap.add_argument("--seconds", type=float, default=0, help="0 = until Ctrl+C")
    ap.add_argument("--outage", type=float, default=0, help="stop the sender for N s halfway through (reconnection test)")
    a = ap.parse_args()
    live = SyntheticLive(a.port, a.fps, a.height, a.segment)
    print(f"Encoder: {'h264_nvenc (GPU)' if live.nvenc else 'libx264 (CPU)'}")
    live.start_encoder()
    print(f"Synthetic live stream ready: {live.url}", flush=True)
    try:
        t0 = time.time()
        cut_done = False
        while a.seconds <= 0 or time.time() - t0 < a.seconds:
            time.sleep(0.5)
            if a.outage and not cut_done and time.time() - t0 > max(10, a.seconds / 2 if a.seconds else 20):
                print(f"Simulated outage of {a.outage:.0f} s", flush=True)
                live.stop_encoder()
                time.sleep(a.outage)
                live.start_encoder()
                print("Sender restored", flush=True)
                cut_done = True
    except KeyboardInterrupt:
        pass
    finally:
        live.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
