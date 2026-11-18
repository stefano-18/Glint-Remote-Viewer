# Test results

**Date:** 2026-11-18.
**Machine:** Ryzen 5 5600X, RTX 3060 12 GB, 16 GB RAM, Windows 11 with **Smart App Control on**.
**Software:** libmpv v0.42.0 (shinchiro build 20261111), Streamlink 8.6.3, PySide6 6.12, Python 3.13.16.

> Tests with the synthetic source do **not** prove that a real PS5 works. They validate the transport, the player, the interface and the logic.

## 1. Automated tests (`pytest`, 42 of 42 passing)
| File | What it covers |
|---|---|
| `tests/test_logic.py` (36) | Valid and invalid URLs, profiles, real Streamlink options, catch-up (hysteresis and jump cooldown), retry backoff, settings with corrupt data, secret scrubbing in logs, segment tracker, quality selection, private YouTube classification |
| `tests/test_bridge_synthetic.py` (4) | Real Streamlink against local HLS: opening, delay, sender outage, source down |
| `tests/test_session_synthetic.py` (2) | Full session: connect, signal lost, automatic reconnection, disconnect; error without retry |

In addition, `pyflakes` reports nothing and there are no hard-coded credentials.

## 2. Real playback with libmpv (the app's `--bench` mode)
Every result is **measured**, except the delays, which are **estimated** from each segment's timestamp.

| Test | Result |
|---|---|
| libmpv loads | Yes, `mpv v0.42.0-38-gbcde6b93c` |
| GPU decoding | `Using hardware decoding (d3d11va)`, `d3d11[nv12]` format, no copies |
| Audio | AAC 48 kHz stereo over WASAPI |
| Volume, mute, fullscreen | Each action changes mpv's and the window's real state (`volume=50`, `mute=true/false`, `fullscreen=true/false`) |
| Quality change | Twitch 1080p → 720p30: reconnects in about 1 s and the resolution becomes 1280×720 |
| Mode change | Balanced → Ultra: reconnects in about 1 s with the new parameters |
| Sender outage (synthetic) | Detects "Signal lost", retries and plays again 1.4 s after the sender returns |
| Invalid URL or non-existent YouTube video | Clear message ("YouTube does not allow playing this video"), no retry loop, no crash |
| Private YouTube | Classification covered by unit tests using the plugin's real messages. **Not tested with a real private stream**, as none was available |
| Closing | The process exits cleanly and no `pythonw`/`python` processes remain |

### The three modes, run from the final package (synthetic 1080p60, 40 s per mode)
| Mode | Shown FPS | Dropped | Buffer | Behind live edge | **Delay since ingest** | CPU (1 core, median/max) | RAM |
|---|---|---|---|---|---|---|---|
| Ultra | 60.0 | 0 | 1.4 s | 1.4 s | **2.1 s** | 13.9 % / 27.7 % | 294 MB |
| Balanced | 60.0 | 0 | 2.6 s | 2.7 s | **3.5 s** | 7.7 % / 17.3 % | 293 MB |
| Stability | 60.0 | 0 | 3.1 s | 3.3 s | **3.9 s** | 7.8 % / 15.7 % | 293 MB |

- The synthetic source uses 1 s segments and the same clock as the PC.
- The source's ffmpeg encoder was running on the same machine at the same time.

### Real public live streams
| Source | Result |
|---|---|
| Twitch (public channel, 1080p, balanced mode) | 1920×1080, GPU, 0 dropped, about 3 % CPU, 7–8 Mbit/s, about 2 s behind the live edge |
| YouTube (public live stream, 1080p30) | GPU, 0 dropped, 4 s buffer. Delay shows "—" because YouTube sends no PDT |

**Segment arrival relative to the platform timestamp** (`tools/platform_latency.py`, clock corrected):

| Platform | Median |
|---|---|
| Twitch, low latency | 0.07–0.12 s |
| Twitch, normal | 4.9 s |
| YouTube | 5 s segments, no PDT |

## 3. Portable package
| Test | Result |
|---|---|
| PyInstaller `.exe` | **Blocked** by Smart App Control (CodeIntegrity events 3033/3077). Dropped |
| Package with the official signed runtime and `GlintRemote-Viewer.cmd` | Opens and closes correctly with Smart App Control on |
| The same package with the "downloaded from the Internet" mark on all 293 binaries | Opens correctly, no block events |
| ZIP extracted to a different folder, playback | 1080p60, GPU, AAC, 0 dropped |
| Isolation | `sys.path` only contains package folders, thanks to `python313._pth` |
| ZIP contents | No development tools (pip, pytest, PyInstaller…), no `.venv`, no settings. **0 files** contain the user name or build-machine paths |
| libmpv hash | Matches the published SHA-256 (`273c079b…8452`) |

## 4. Pending
| # | Test |
|---|---|
| P1 | A real PS5 broadcast to Twitch following `GUIDE_BROADCASTER.md` |
| P2 | Seeing and hearing the real game while the broadcaster plays normally and both talk on Discord |
| P3 | Real total delay ("now!" method, `GUIDE_VIEWER.md` §7) |
| P4 | The broadcaster noticing no lag in their online game while broadcasting |
| P5 | A real private YouTube stream (check the notice and the browser button) |
