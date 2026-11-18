# Guide: watching with Glint Remote Viewer

Glint Remote Viewer is a Windows player for watching your friend's PS5 broadcast **with the lowest delay Twitch allows**. It decodes the video on your graphics card, so you can keep Discord and your browser open at the same time.

## 1. Download and open the program

1. On the project's GitHub page, open **Releases** (on the right) and download **`GlintRemote-Windows-x64.zip`**.
2. Right-click the ZIP → **Extract All…** → **Extract**.
3. Open the `GlintRemote-Viewer` folder and double-click **`GlintRemote-Viewer.cmd`**. A black window may flash for a moment: that's normal.

- **Nothing to install**, not even Python. It's a portable folder: you can move the whole `GlintRemote-Viewer` folder anywhere you like (for example, to the Desktop).
- **Don't move the `.cmd` on its own, without its folder:** it needs the `runtime` folder.
- **Why a `.cmd` and not an `.exe`?** Windows 11 ships with **Smart App Control**, which blocks any new `.exe` without a digital signature. The program uses the official Python runtime, which is digitally signed and lives inside `runtime`. That way it works without turning off any protection.
- **Shortcut:** right-click `GlintRemote-Viewer.cmd` → **Show more options** → **Send to** → **Desktop (create shortcut)**.
- **If Windows asks "Do you want to run this file?"** (this happens with files downloaded from the Internet): choose **Run**.
- **Uninstall:** delete the `GlintRemote-Viewer` folder. To also remove your settings, delete `%APPDATA%\GlintRemote` (paste that path into File Explorer's address bar to find it).

## 2. Connect

1. Your friend starts broadcasting from their PS5 (see [GUIDE_BROADCASTER.md](GUIDE_BROADCASTER.md)).
2. In the top bar, type **their Twitch channel name**.
   - Either the name alone (`theirname`) or the full link (`https://www.twitch.tv/theirname`) works.
   - YouTube live links work too, although Twitch gives noticeably less delay.
3. Press **Connect** or **Enter**.
4. **If your friend hasn't started yet,** you'll see "Waiting for the broadcast". You don't need to do anything: the program keeps retrying and connects as soon as they go live.

The program remembers your recent channels. Open the drop-down in the top bar to pick one.

### YouTube streams

- **Public or unlisted:** paste the link to the live stream and press **Connect**. For example `https://www.youtube.com/watch?v=…` or `https://youtu.be/…`. You can also type `@channelname` to open that channel's current live stream. It plays inside the program.
- **Private:** the program can't play it, because YouTube requires an authorised Google account and the program never asks for or stores passwords or sessions. You'll see the notice "This YouTube stream is PRIVATE". Press **Open in browser**: it opens in your normal browser (Chrome, Edge…) with your Google session. If your account is authorised, you'll see it there.
- With YouTube the delay is longer than with Twitch, and the delay statistics show "—", because YouTube doesn't send timestamps.

The **Open in browser** button works with any channel or link. If you were watching it in the program, it disconnects so you don't hear the stream twice.

## 3. Watch and listen

| Action | How |
|---|---|
| Fullscreen | **F11**, **double-click** the video, or the four-corners button |
| Exit fullscreen | **Esc** or **F11** |
| Volume | The bar at the bottom, or the **↑** / **↓** keys |
| Mute | The speaker button or the **M** key |
| Hide the side panel | The panel button or the **P** key |
| Audio output | Panel → **Audio** → choose headphones or speakers |

Glint Remote's volume is independent from Discord's, so you can set each one separately. For finer control use the Windows **Volume mixer**: right-click the speaker icon on the taskbar.

## 4. Choose the mode

In the panel → **Mode**. Each mode changes the real buffers of the player and of the download:

| Mode | What it's for | Player delay (measured)* |
|---|---|---|
| **Ultra low latency** | As close to live as possible. If your Internet or your friend's hiccups, it may stutter a little. | ≈ 1.7 s |
| **Balanced** (recommended) | Little delay and smooth playback. If you fall behind, it catches up on its own. | ≈ 3.1 s |
| **Maximum stability** | For unreliable connections. More delay, almost no stalls. Lowers the quality by itself after repeated stalls. Twitch in normal mode adds about 5 s. | ≈ 4.4 s + ≈ 5 s |

\*Measured with a test stream on your own PC: the time from the platform publishing a frame until you see it. With Twitch in low latency, the video arrives about 0.1 s after it's published.

On top of that comes the time the PS5 and Twitch need to process the picture before publishing it. This program doesn't control that part; it's usually a few seconds. The real total delay can only be measured with your friend's PS5 (see section 7).

**Quality:** in the panel → **Quality**. **Automatic** uses the best quality your friend broadcasts. If your Internet is tight, pick a lower one (for example 720p60).

## 5. The statistics

The colour of each value shows where it comes from: **white** = measured, **amber** = estimated, **—** = no data yet. Hover over a value to see what it means. The program never fills in a made-up value.

| Value | What it means |
|---|---|
| Resolution / Stream FPS | What Twitch is sending. If your friend broadcasts at 30 fps you'll see 30; no frames are invented. |
| Shown FPS | Frames actually drawn on your screen. |
| Dropped frames | If it keeps rising, try **Balanced** mode or a lower quality. |
| Decoding | It should say **GPU (d3d11va)**. If it says **CPU**, check Options → GPU decoding. |
| Download (network) | How fast the stream is reaching you. |
| Buffer | Seconds of video stored ahead. More buffer means fewer stalls but more delay. |
| Behind live edge | How far behind the latest segment Twitch has published you are (estimated). |
| Delay since ingest | From Twitch receiving that moment until you see it. It's estimated and relies on the Windows clock being correct. |
| Buffering stalls | Stalls in the last 2 minutes. |
| Catch-up | While it's catching up you'll see 1.04× or 1.06×. The audio pitch doesn't change. |

## 6. Problems and fixes

**No sound**
1. Check whether the speaker button is red (muted). Press **M**.
2. Panel → **Audio** → choose the right output. If in doubt, choose "System default".
3. Windows Volume mixer → check that Glint Remote isn't at 0.
4. If your friend's broadcast has no sound for them either, the problem is on their PS5 (see their guide).

**Black, frozen or stuttering picture**
1. Check the status at the top right. If it says "Waiting for the broadcast", your friend isn't live.
2. If "Dropped frames" rises a lot: Panel → Options → **GPU decoding → D3D11VA**. If it was already set, try **Automatic**.
3. Update your graphics driver.
4. If it happens in every mode, ask your friend to drop to 720p (see their guide).

**It disconnects**
- With "Reconnect automatically" on (the default), it comes back by itself.
- If it takes too long, press **Disconnect** and then **Connect**.
- If it cuts out often, use **Maximum stability**.

**Too much delay**
1. Use **Ultra low latency** mode.
2. Check that "Catch up with the live edge" is on.
3. Make sure your friend has **Low latency** enabled on Twitch (their guide, section 1, step 4). That has the biggest effect.
4. A network cable helps more than any setting: on your PC and, above all, on their PS5.

**Export a log to look into a problem:** Panel → **Diagnostics** → **Export log…**. The file contains no passwords, tokens, personal paths or private IPs.

## 7. Measuring the real delay (with your friend)

At a precise moment, your friend says "now!" on Discord as they press pause in the game. You use your phone's stopwatch from hearing "now!" until you see the pause in Glint Remote. Do it 3 times and take the average. Discord itself takes about 0.2 s, so the result is the total delay within about ±0.3 s.

## 8. Closing

Close the window with the **X**. It disconnects and saves your settings, and leaves nothing running in the background.
