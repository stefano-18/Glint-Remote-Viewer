"""Builds the portable release in dist/GlintRemote-Viewer/.

Layout: the official Python runtime (pythonw.exe and its DLLs, digitally signed, neither modified
nor renamed) in runtime/, the application in runtime/app, and a GlintRemote-Viewer.cmd launcher
that runs `runtime/pythonw.exe -m viewer`. This is the use Python documents for portable apps.
A generated executable (e.g. PyInstaller) has no signature or reputation, and Windows 11 Smart App
Control blocks it.

Usage: python tools/build_portable.py   (from the project's .venv)
"""
from __future__ import annotations

import compileall
import importlib.metadata as md
import re
import shutil
import sys
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "GlintRemote-Viewer"
RT = OUT / "runtime"
PYHOME = Path(sys.base_prefix)
RUNTIME_REQS = ["streamlink", "PySide6_Essentials", "python-mpv", "psutil"]
STDLIB_SKIP = {"test", "tkinter", "idlelib", "turtledemo", "ensurepip", "venv", "lib2to3", "pydoc_data",
               "site-packages", "__pycache__", "unittest", "turtle.py", "doctest.py"}
DLLS_SKIP = re.compile(r"(?i)^(_tkinter|tcl|tk|_test|xxlimited|winsound|_msi)")
PTH_NAME = "python313._pth"
CRLF = bytes([13, 10])
LAUNCHER_LINES = [
    "@echo off",
    r"rem Glint Remote Viewer - portable launcher (official signed Python runtime in runtime\)",
    r'start "" "%~dp0runtime\pythonw.exe" -m viewer %*',
]
PTH_LINES = ["Lib", "DLLs", "Lib/site-packages", "app", "import site"]


def dist_closure(names: list[str]) -> list[md.Distribution]:
    env = default_environment()
    seen: dict[str, md.Distribution] = {}
    todo = list(names)
    while todo:
        req = Requirement(todo.pop())
        key = req.name.lower().replace("_", "-")
        if key in seen:
            continue
        try:
            dist = md.distribution(req.name)
        except md.PackageNotFoundError:
            continue
        seen[key] = dist
        for r in dist.requires or []:
            rr = Requirement(r)
            if rr.marker is None or rr.marker.evaluate({**env, "extra": ""}):
                todo.append(str(rr))
    return list(seen.values())


def copy_tree(src: Path, dst: Path, skip: set[str]) -> None:
    for item in src.iterdir():
        if item.name in skip:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", "test", "tests"))
        else:
            shutil.copy2(item, target)


def main() -> int:
    dll = ROOT / "vendor" / "libmpv-2.dll"
    if not dll.exists():
        print("vendor/libmpv-2.dll is missing (run build.ps1)")
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    RT.mkdir(parents=True)

    # 1. Official Python runtime, unmodified (digitally signed files).
    for name in ("pythonw.exe", "python.exe", "python313.dll", "python3.dll", "vcruntime140.dll",
                 "vcruntime140_1.dll"):
        if (PYHOME / name).exists():
            shutil.copy2(PYHOME / name, RT / name)
    (RT / "DLLs").mkdir()
    for f in (PYHOME / "DLLs").iterdir():
        if f.suffix.lower() in (".pyd", ".dll") and not DLLS_SKIP.match(f.name):
            shutil.copy2(f, RT / "DLLs" / f.name)
    (RT / "Lib").mkdir()
    copy_tree(PYHOME / "Lib", RT / "Lib", STDLIB_SKIP)

    # 2. Runtime dependencies (only the dependency closure, no development tools).
    sp = RT / "Lib" / "site-packages"
    sp.mkdir()
    dists = dist_closure(RUNTIME_REQS)
    for dist in dists:
        for f in dist.files or []:
            src = Path(dist.locate_file(f))
            if not src.is_file() or ".." in f.parts or {"__pycache__", "tests", "_tests"} & set(f.parts):
                continue
            dst = sp / Path(*f.parts)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    # Qt: drop what isn't used (software OpenGL, translations, tools). The UI is in English.
    qt = sp / "PySide6"
    for pat in ("opengl32sw.dll", "*.exe", "Qt6Quick*.dll", "Qt6Qml*.dll", "Qt6Pdf*.dll"):
        for f in qt.glob(pat):
            f.unlink()
    shutil.rmtree(qt / "translations", ignore_errors=True)

    # 3. The application and libmpv.
    app = RT / "app"
    shutil.copytree(ROOT / "viewer", app / "viewer", ignore=shutil.ignore_patterns("__pycache__"))
    (app / "vendor").mkdir()
    shutil.copy2(dll, app / "vendor" / dll.name)

    # 4. Search paths (isolated: ignores PYTHONPATH and any Python installed on the system).
    (RT / PTH_NAME).write_bytes(CRLF.join(x.encode() for x in PTH_LINES) + CRLF)

    # 5. Precompile for faster start-up (without storing the build machine's absolute path).
    for d in (RT / "Lib", app):
        compileall.compile_dir(d, quiet=1, workers=0, stripdir=str(OUT), prependdir="GlintRemote-Viewer")

    # 6. Launcher, licences and README.
    (OUT / "GlintRemote-Viewer.cmd").write_bytes(CRLF.join(x.encode("ascii") for x in LAUNCHER_LINES) + CRLF)
    shutil.copytree(ROOT / "LICENSES", OUT / "LICENSES")
    shutil.copy2(PYHOME / "LICENSE.txt", OUT / "LICENSES" / "Python-LICENSE.txt")
    shutil.copy2(ROOT / "LICENSE", OUT / "LICENSE.txt")
    shutil.copy2(ROOT / "README_PORTABLE.txt", OUT / "README.txt")
    print(f"Done: {OUT}  ({len(dists)} packages: {', '.join(sorted(d.metadata['Name'] for d in dists))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
