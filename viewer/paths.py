"""Location of libmpv-2.dll: <root>/vendor, both in the repository and in the portable package
(runtime/app/vendor)."""
from __future__ import annotations

import os
from pathlib import Path


def vendor_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "vendor"


def prepare_mpv_dll() -> Path:
    d = vendor_dir()
    if hasattr(os, "add_dll_directory") and d.exists():
        os.add_dll_directory(str(d))
    os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
    return d
