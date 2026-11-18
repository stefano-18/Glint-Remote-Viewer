"""Persistent settings in %APPDATA%\\GlintRemote\\settings.json (no credentials)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .profiles import DEFAULT_PROFILE, PROFILES

HWDEC_CHOICES = ("d3d11va", "auto-safe", "no")
QUALITY_CHOICES = ("best", "1080p60", "1080p", "936p60", "720p60", "720p", "480p", "worst")
HISTORY_MAX = 10


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "GlintRemote"


@dataclass
class Settings:
    last_source: str = ""
    history: list[str] = field(default_factory=list)
    profile: str = DEFAULT_PROFILE
    quality: str = "best"
    volume: int = 80
    muted: bool = False
    audio_device: str = "auto"
    hwdec: str = "d3d11va"
    auto_reconnect: bool = True
    catchup_enabled: bool = True
    show_stats: bool = True
    allow_local_test: bool = False

    def remember(self, label: str) -> None:
        label = label.strip()[:300]
        if not label:
            return
        self.last_source = label
        self.history = [label] + [h for h in self.history if h != label]
        self.history = self.history[:HISTORY_MAX]

    def forget(self, label: str) -> None:
        self.history = [h for h in self.history if h != label]


def _validate(raw: dict) -> Settings:
    s = Settings()
    if not isinstance(raw, dict):
        return s

    def get(name, typ, ok=lambda v: True):
        v = raw.get(name)
        return v if isinstance(v, typ) and not (typ is int and isinstance(v, bool)) and ok(v) else getattr(s, name)

    s.last_source = get("last_source", str, lambda v: len(v) <= 300)
    hist = raw.get("history")
    if isinstance(hist, list):
        s.history = [h for h in hist if isinstance(h, str) and 0 < len(h) <= 300][:HISTORY_MAX]
    s.profile = get("profile", str, lambda v: v in PROFILES)
    s.quality = get("quality", str, lambda v: v in QUALITY_CHOICES)
    s.volume = get("volume", int, lambda v: 0 <= v <= 130)
    s.muted = get("muted", bool)
    s.audio_device = get("audio_device", str, lambda v: 0 < len(v) <= 400)
    s.hwdec = get("hwdec", str, lambda v: v in HWDEC_CHOICES)
    s.auto_reconnect = get("auto_reconnect", bool)
    s.catchup_enabled = get("catchup_enabled", bool)
    s.show_stats = get("show_stats", bool)
    s.allow_local_test = get("allow_local_test", bool)
    return s


def load(path: Path | None = None) -> Settings:
    path = path or app_dir() / "settings.json"
    try:
        return _validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return Settings()


def save(settings: Settings, path: Path | None = None) -> None:
    path = path or app_dir() / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
