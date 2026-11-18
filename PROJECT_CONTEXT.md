# Glint Remote Viewer: project context

**Goal:** from a Windows PC, watch and hear someone else's PS5 gameplay in another house, with the lowest possible delay. No capture card, no console modification, free, and without affecting the game or Discord.

## Architecture

```
PS5 (hardware encoder, "Broadcast")
  → Twitch (low-latency HLS) or YouTube
  → Internet (HTTPS)
  → Glint Remote Viewer:
      Streamlink (in-process: low-latency, prefetch, per-segment timestamps)
        → custom mpv_stream_cb (one memmove per block)
        → libmpv: D3D11VA zero-copy + gpu-next/d3d11
        → native window inside PySide6
```

## Code map

| Path | Purpose |
|---|---|
| `viewer/source.py` | Validates the channel or URL. Allow-list: Twitch, YouTube, and 127.0.0.1 in test mode |
| `viewer/bridge.py` | Streamlink, segment tracker, YouTube error classification, clock offset |
| `viewer/player.py` | libmpv with the custom protocol |
| `viewer/session.py` | Connect, reconnect, catch-up, adaptive quality and metrics |
| `viewer/profiles.py` | The three modes |
| `viewer/ui.py` | Interface, keyboard shortcuts, `--bench` mode and screenshots |
| `viewer/theme.py` | Design tokens, QSS and SVG icons |
| `viewer/config.py` | Settings in `%APPDATA%\GlintRemote` |
| `tools/` | Synthetic source, platform latency meter, benchmark summary, libmpv check, portable build and ZIP |

See also [DECISIONS.md](DECISIONS.md), [PROGRESS.md](PROGRESS.md), [TEST_RESULTS.md](TEST_RESULTS.md) and [NEXT_STEPS.md](NEXT_STEPS.md).
