# Next steps

1. **Test with a real PS5.** These are tests P1–P5 in [TEST_RESULTS.md](TEST_RESULTS.md).
   - The broadcaster follows [GUIDE_BROADCASTER.md](GUIDE_BROADCASTER.md).
   - Measure the total delay with the "now!" method over Discord ([GUIDE_VIEWER.md](GUIDE_VIEWER.md) §7).
   - If Ultra mode stutters on the real network, tune `cache-secs` and `hls-live-edge` in `viewer/profiles.py`.
2. **Code signing** (for example the free open-source signing offered by SignPath Foundation). It would allow shipping a native `GlintRemote-Viewer.exe` instead of the `.cmd` launcher.
3. **Low-latency plan B** (only if ever needed). A wired PC at the broadcaster's receives the PS5 over Remote Play (chiaki-ng) and forwards it over a private VPN. It means loading the broadcaster's equipment.
