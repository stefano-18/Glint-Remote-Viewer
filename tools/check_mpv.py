"""Checks that libmpv loads and lists the cache/latency options that matter."""
import os
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "vendor"
os.add_dll_directory(str(VENDOR))
os.environ["PATH"] = str(VENDOR) + os.pathsep + os.environ.get("PATH", "")

import mpv  # noqa: E402

m = mpv.MPV()
print("mpv:", m.mpv_version)
wanted = ("cache", "readahead", "hwdec", "video-sync", "untimed", "gpu-api", "vo", "audio-buffer", "demuxer-lavf-o")
opts = sorted(o for o in m.options if any(w in o for w in wanted))
print("\n".join(opts))
m.terminate()
sys.exit(0)
