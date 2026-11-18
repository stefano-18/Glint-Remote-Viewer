# Implementation status (v1.0.0)

| Area | Status |
|---|---|
| Player (Streamlink in-process, libmpv with D3D11VA) | Done; tested with synthetic sources and real Twitch and YouTube streams |
| Three modes with real parameters and catch-up | Done and measured |
| Reconnection and waiting for the broadcast | Done; tested (simulated outage) |
| Quality, adaptive quality, audio, fullscreen, keyboard shortcuts | Done and tested |
| Measured/estimated statistics, clock correction | Done |
| Public and unlisted YouTube | Done; tested (public) |
| Private YouTube, with a notice and an open-in-browser button | Done. Covered by unit tests. A real private stream is still pending |
| Settings and history without credentials | Done |
| Portable package compatible with Smart App Control | Done and tested |
| Documentation (English) | Done |
| CI (lint, tests, package) | Done |
| Test with a real PS5 | **Pending** (TEST_RESULTS §4) |

**Overall:** implemented and tested with test sources and real public streams. The test with a real PS5 is still pending.
