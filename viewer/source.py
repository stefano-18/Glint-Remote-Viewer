"""Validation and normalisation of what the user types (channel name or URL)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse, urlunparse

TWITCH_LOGIN = re.compile(r"^[A-Za-z0-9_]{4,25}$")
YT_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_HANDLE = re.compile(r"^@[A-Za-z0-9._-]{3,30}$")
YT_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")

TWITCH_HOSTS = {"twitch.tv", "www.twitch.tv", "m.twitch.tv"}
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
# twitch.tv paths that are not channels.
TWITCH_RESERVED = {
    "directory", "videos", "settings", "p", "downloads", "jobs", "search", "subscriptions",
    "inventory", "wallet", "drops", "friends", "messages", "turbo", "prime", "store",
}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
MAX_LEN = 300


class SourceError(ValueError):
    """Invalid input; the message is meant to be shown to the user."""


@dataclass(frozen=True)
class Source:
    platform: str  # "twitch" | "youtube" | "local"
    url: str       # URL handed to Streamlink
    label: str     # short text for the UI / history

    @property
    def is_twitch(self) -> bool:
        return self.platform == "twitch"

    @property
    def web_url(self) -> str | None:
        """Public page of the stream, to open it in the user's browser (None for local tests)."""
        return None if self.platform == "local" else self.url


def _twitch(login: str) -> Source:
    login = login.lower()
    return Source("twitch", f"https://www.twitch.tv/{login}", login)


def parse_source(text: str, allow_local: bool = False) -> Source:
    t = (text or "").strip()
    if not t:
        raise SourceError("Type your friend's Twitch channel name or the live stream URL.")
    if len(t) > MAX_LEN or any(c.isspace() for c in t):
        raise SourceError("That address is not valid (too long or contains spaces).")

    # Bare Twitch channel name.
    if TWITCH_LOGIN.match(t):
        return _twitch(t)
    # Bare YouTube @handle.
    if YT_HANDLE.match(t):
        return Source("youtube", f"https://www.youtube.com/{t}/live", t)

    if "://" not in t:
        t = "https://" + t
    u = urlparse(t)
    host = (u.hostname or "").lower()
    parts = [p for p in u.path.split("/") if p]

    if u.scheme in ("http", "https") and host in TWITCH_HOSTS:
        if parts and TWITCH_LOGIN.match(parts[0]) and parts[0].lower() not in TWITCH_RESERVED:
            if len(parts) > 1 and parts[1] in ("videos", "clip", "clips"):
                raise SourceError("That is a recorded video or clip; use the link of the live channel.")
            return _twitch(parts[0])
        raise SourceError("No Twitch channel found in that address.")

    if u.scheme in ("http", "https") and (host in YOUTUBE_HOSTS or host == "youtu.be"):
        vid = ""
        if host == "youtu.be" and parts:
            vid = parts[0]
        elif u.path == "/watch":
            vid = parse_qs(u.query).get("v", [""])[0]
        elif len(parts) >= 2 and parts[0] == "live":
            vid = parts[1]
        if vid:
            if not YT_VIDEO_ID.match(vid):
                raise SourceError("The YouTube video ID is not valid.")
            return Source("youtube", f"https://www.youtube.com/watch?v={vid}", vid)
        if parts and YT_HANDLE.match(parts[0]):
            return Source("youtube", f"https://www.youtube.com/{parts[0]}/live", parts[0])
        if len(parts) >= 2 and parts[0] == "channel" and YT_CHANNEL_ID.match(parts[1]):
            return Source("youtube", f"https://www.youtube.com/channel/{parts[1]}/live", parts[1])
        raise SourceError("That YouTube address is not recognised. Use the link of the live stream.")

    if allow_local and u.scheme in ("http", "https") and host in LOCAL_HOSTS and u.path.endswith(".m3u8"):
        clean = urlunparse((u.scheme, u.netloc, u.path, "", "", ""))
        return Source("local", "hls://" + clean, "Local test")

    raise SourceError("Only Twitch channels and YouTube live streams are supported.")
