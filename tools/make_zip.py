"""Packs dist/GlintRemote-Viewer into dist/GlintRemote-Windows-x64.zip and writes its SHA-256."""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "dist" / "GlintRemote-Viewer"
OUT = ROOT / "dist" / "GlintRemote-Windows-x64.zip"
FORBIDDEN_NAMES = {".env", "settings.json"}
FORBIDDEN_SUFFIXES = (".log",)


def main() -> int:
    if not (SRC / "GlintRemote-Viewer.cmd").exists():
        print("dist/GlintRemote-Viewer is missing: run build.ps1 first")
        return 1
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(SRC.rglob("*")):
            if not f.is_file() or f.name in FORBIDDEN_NAMES or f.name.endswith(FORBIDDEN_SUFFIXES):
                continue
            z.write(f, f"GlintRemote-Viewer/{f.relative_to(SRC).as_posix()}")
            n += 1
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    OUT.with_name(OUT.name + ".sha256").write_text(f"{sha}  {OUT.name}\n")
    print(f"{OUT.name}: {n} archivos, {OUT.stat().st_size / 1e6:.1f} MB, sha256 {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
