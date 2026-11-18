"""Metrics tagged with their origin (measured / estimated / unknown) and a log free of sensitive data."""
from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

MEASURED, ESTIMATED, UNKNOWN = "measured", "estimated", "unknown"


@dataclass(frozen=True)
class Metric:
    text: str
    kind: str = MEASURED

    @staticmethod
    def unknown() -> "Metric":
        return Metric("—", UNKNOWN)


_QS_SECRET = re.compile(
    r"(?i)\b(token|sig|signature|auth|oauth|key|password|passwd|secret|client[-_]?integrity|"
    r"session|sid|nauth|nauthsig|access_token)=([^&\s\"']+)")
_HEADER_SECRET = re.compile(r"(?i)\b(authorization|cookie|client-integrity)\s*[:=]\s*[^\r\n]+")
_OAUTH = re.compile(r"(?i)\boauth\s+[a-z0-9]{10,}")
_USER_PATH = re.compile(r"(?i)([a-z]:[\\/]+users[\\/]+)[^\\/\s]+")
_PRIVATE_IP = re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|"
                         r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")
_LONG_QUERY = re.compile(r"(https?://[^\s?]+)\?[^\s]{60,}")


def sanitize(text: str) -> str:
    t = str(text)
    t = _HEADER_SECRET.sub(lambda m: f"{m.group(1)}: <hidden>", t)
    t = _OAUTH.sub("OAuth <hidden>", t)
    t = _QS_SECRET.sub(lambda m: f"{m.group(1)}=<hidden>", t)
    t = _LONG_QUERY.sub(lambda m: f"{m.group(1)}?<parameters hidden>", t)
    t = _USER_PATH.sub(lambda m: f"{m.group(1)}<user>", t)
    t = _PRIVATE_IP.sub("<private-ip>", t)
    return t


class LogBuffer:
    """In-memory log (never written to disk unless the user exports it)."""

    def __init__(self, maxlen: int = 3000):
        self._lines: deque[str] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self.errors = 0

    def add(self, level: str, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} [{level}] {sanitize(msg)}"
        with self._lock:
            self._lines.append(line)
            if level in ("error", "fatal"):
                self.errors += 1

    def lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def export(self, path: Path, header: str = "") -> Path:
        body = "\n".join(self.lines())
        path.write_text((sanitize(header) + "\n\n" if header else "") + body + "\n", encoding="utf-8")
        return path


def fmt_seconds(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f} s"


def fmt_bitrate(bps: float | None) -> str:
    if not bps:
        return "—"
    return f"{bps / 1e6:.1f} Mbit/s" if bps >= 1e6 else f"{bps / 1e3:.0f} kbit/s"
