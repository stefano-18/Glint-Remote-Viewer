# Technical decisions

## D1. Video source: the PS5's official "Broadcast" feature
An unmodified PS5 can't run third-party software, so it can't be captured directly. These are the options without a capture card:

| Criterion | Broadcast (PS5) → Twitch/YouTube | Share Screen (PS App) | Remote Play + broadcaster's PC |
|---|---|---|---|
| Unmodified PS5 | Yes | Yes | Yes |
| No PC needed at the broadcaster's | Yes | Yes | No |
| Viewable on Windows | Yes | No, phone only | Yes |
| Load on the broadcaster | None: the PS5 encodes | None | Their PC's |
| Privacy | Twitch public; YouTube can be unlisted | Private | Private |

We chose Broadcast: it meets every other requirement without loading the player's equipment. The trade-off is privacy, which the guides document.

## D2. Twitch is the recommended platform
Measured with public live streams using `tools/platform_latency.py`:

- **Twitch:** 2 s segments and low latency with *prefetch*. Data arrives about 0.1 s after the segment timestamp.
- **YouTube:** 5 s segments and HLS without a usable `PROGRAM-DATE-TIME`, so delay can't be measured or caught up.

Public and unlisted YouTube streams play. Private ones don't (see D7).

## D3. Streamlink inside the same process
We use Streamlink's Python API instead of `streamlink | mpv`:
- No pipe and no second process.
- It lets us instrument the HLS writer to know which segment is on screen.

## D4. Custom `stream_cb` protocol
python-mpv's `MPV.register_stream_protocol` copies data byte by byte in a Python loop. At 1080p60 that spiked the CPU (65 %) and mpv never got to show video. [viewer/player.py](viewer/player.py) registers its own `mpv_stream_cb_add_ro` and copies each block with a single `ctypes.memmove`. Result: 6–8 % of one core.

## D5. Fixed mpv options
| Option | Why |
|---|---|
| `vo=gpu-next`, `gpu-api=d3d11`, `hwdec=d3d11va` | The decoded frame never leaves the GPU |
| `video-sync=audio` | The cheapest mode |
| `interpolation=no` | No invented frames |
| `config=no`, `load_scripts=no` | No third-party configuration gets loaded |

**Watch out:** `MPV[...]` reads *options*, not *properties*. Metrics are read with `_get_property`.

## D6. Catch-up
- The "excess" is the delay behind the newest known segment minus `live_edge × segment duration`. It doesn't depend on the Windows clock.
- With excess, playback speeds up to 1.03–1.06× with scaletempo2, with hysteresis. With little buffer, it doesn't speed up.
- With a large excess it jumps: inside the buffer if it fits, otherwise it reopens the stream. There's always a minimum time between jumps.
- Stability mode never jumps.
- The "delay since ingest" is corrected with the clock offset, measured from Twitch's `Date` header (±0.5 s).

## D7. Private YouTube
- Streamlink's plugin raises no error for private videos: it only logs `Could not get video info - LOGIN_REQUIRED`. We capture that message and classify it (private, members only, not started or unavailable).
- The alternative is the **Open in browser** button: it opens the page in the default browser with the user's own session.
- No cookies or credentials are ever read, extracted or stored.

## D8. No VPN or relay
The platform already handles NAT, CGNAT and HTTPS encryption. No port is opened in either house.

## D9. Licence
GPL-3.0-or-later, because the release ships with libmpv, which is GPL. Qt is dynamically linked (LGPL). Notices are in `LICENSES/`.

## D10. Portable package with the official signed Python runtime, no PyInstaller
- Windows 11 Smart App Control, active on the test machine, blocked the PyInstaller-generated `.exe` ("An Application Control policy has blocked this file", CodeIntegrity events 3033/3077). The reason: it differs on every build and has no signature or reputation.
- So the package ships the official Python runtime **neither modified nor renamed** (`runtime/pythonw.exe` and its DLLs, digitally signed), isolated through `python313._pth`, plus a `GlintRemote-Viewer.cmd` launcher.
- Verified that it opens with Smart App Control on, including with the "downloaded from the Internet" mark on every binary.
- No protection is disabled or bypassed. A native `.exe` would need code signing (see NEXT_STEPS).
- `.pyc` files are compiled with `stripdir`, so no build-machine paths are stored.

## D11. One language: English
Interface, documentation, code comments and commit messages are all in English, so the project is usable from any country.
