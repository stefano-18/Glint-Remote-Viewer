# Guide: broadcasting your game from the PS5

This guide is for **you, the one playing**. You don't need to install anything on a computer or know any programming. Everything happens on the PS5 with the controller, using PlayStation's official **Broadcast** feature. You keep playing exactly as usual, and you can keep talking on Discord.

**What you need:**
- Your PS5, unmodified.
- A free Twitch account (or a YouTube account, see section 7).
- About 10 minutes the first time. After that, going live takes 3 button presses.

> **Privacy:** Twitch broadcasts are **public**. Anyone who finds your channel can watch, and Twitch has no private broadcasts. If you want it to stay low-key, use a channel name that isn't obvious.

---

## 1. First time: create and set up your Twitch account

1. On your phone or computer, go to **twitch.tv** and create a free account (**Sign Up**).
   - Your **username** is your channel name. Send it to your friend: it's all they need to watch you.
2. Confirm your email address with the code Twitch sends you.
3. **Recommended:** turn on **two-factor authentication** in Twitch (**Settings → Security and Privacy**). Sony warns that some services require it; without it the broadcast can get stuck on "Preparing…".
4. Check that the **latency mode** is set to **Low latency**. This is what keeps the delay short for your friend.
   - Path: twitch.tv → your profile picture → **Creator Dashboard** → **Settings** → **Stream** → **Latency mode: Low latency**.
   - New accounts usually have it set like this already. If the menu wording differs, look for "latency" on that page.
5. Optional: on the same page you can turn off **Store past broadcasts** so Twitch doesn't keep recordings.

## 2. First time: link Twitch to your PS5

On the PS5:

1. **Settings** → **Users and Accounts** → **Linked Services**.
2. Choose **Twitch** → **Link Account**.
3. A **QR code** and a **code** appear.
   - Scan the QR code with your phone, or go to **twitch.tv/activate** and type the code.
4. When you're done, **Linked** appears next to Twitch.

## 3. First time: broadcast settings

**Settings** → **Captures and Broadcasts** → **Broadcasts**:

- **Video Quality:** choose it based on your **upload** speed. You can check that speed in section 8.

  | Your upload speed | Choose | Why |
  |---|---|---|
  | 10 Mbps or more | **1080p, 60 fps** | Best quality |
  | 6 to 10 Mbps | **720p, 60 fps** | Smooth without saturating your connection |
  | 4 to 6 Mbps | **720p, 30 fps** | Stable on tight connections |
  | Less than 4 Mbps | The lowest option | Otherwise you'll get stalls and lag in your online games |

  The exact options shown depend on the service. If in doubt, start with **720p 60 fps**: it's the best balance for keeping your online games unaffected.

- **Audio:** **turn off** microphone audio and **party audio**.
  - You're already talking on Discord, so your voice doesn't need to go into the broadcast. If it did, your friend would hear you twice, delayed and with echo.
  - **Game audio is always included.**
- **Overlays / Camera / Chat to Speech:** you can leave them off.

## 4. Every time you play: start broadcasting

1. With the game open, press the **Create** button on the controller (the small button to the left of the touch pad).
2. Select **Broadcast**.
3. Choose **Twitch**.
4. Enter any title, for example "game".
5. Select **Go Live**.
6. A broadcast card appears. That's it: **go back to the game and play normally**.

Tell your friend on Discord that you're live. They type your channel name in their app and watch you. If they were already connected and waiting, it picks you up automatically.

**What's the link?** It's simply `twitch.tv/YOUR_USERNAME`. Your username is enough.

## 5. While you play

- **You play exactly as usual**, with your controller and on your TV. The PS5 encodes the video with its own hardware, so broadcasting doesn't cost the game any FPS.
- **Discord** keeps working the same way, on the PS5 or on your phone.
- Some games **block certain scenes**, such as cutscenes or stores. During those moments your friend sees a notice screen instead of the game. That's normal and it goes back by itself.
- The broadcast pauses by itself on some system screens.

## 6. Stop broadcasting

1. Press the **PS** button. The control center opens.
2. Select the **broadcast** card.
3. Select **Stop Broadcast**.

There's also **Pause Broadcast**, to cut it for a moment without ending it.

## 7. Alternative: broadcasting on YouTube

Twitch gives **less delay** and is simpler. Use YouTube only if you don't want the broadcast to be public.

**What each YouTube privacy setting means:**

| Privacy | Who can watch | Does it work in your friend's app? |
|---|---|---|
| **Public** | Anyone; it shows up in search | Yes |
| **Unlisted** | Only people with the link. It doesn't show up in search, but anyone who has the link can pass it on. | **Yes (recommended)** |
| **Private** | Only the Google accounts you authorise | **Not inside the app.** Your friend would have to open it in their browser with their account, and it hasn't been verified that YouTube lets you invite other accounts to a private live stream sent from the PS5. |

**First time:**

1. **Enable live streaming on YouTube.** On your phone or computer, sign in at **youtube.com** → your picture → **YouTube Studio** → **Create** → **Go live**. YouTube may ask you to verify your phone number. The first activation **can take up to 24 hours**, so do it in advance.
2. **Link YouTube on the PS5:** **Settings** → **Users and Accounts** → **Linked Services** → **YouTube** → **Link Account**, and follow the on-screen steps.
3. **Quality and audio** are set up exactly as in section 3: quality based on your upload speed, microphone and party audio off.

**Every time:**

1. **Create** button → **Broadcast** → **YouTube**.
2. If a **privacy** option appears on that screen, choose **Unlisted**.
   - If it doesn't appear, Sony says privacy is set in your linked account. Right after going live, open **YouTube Studio** → **Content** → **Live**, open the broadcast and change **Visibility** to **Unlisted**. Check on your own channel that it stuck.
3. Select **Go Live**.
4. **Send your friend the link:** in YouTube Studio, or in the YouTube phone app → your channel → the live stream → **Share** → **Copy link**. Send it over Discord. It looks like `https://youtu.be/XXXXXXXXXXX`.

## 8. Problems and fixes

**Is your Internet good enough to broadcast?** Check your upload speed under **Settings** → **Network** → **Connection Status** → **Test Internet Connection**. Look at the **upload speed** and use the table in section 3.

| Problem | What to do |
|---|---|
| It stays on "Preparing…" and never starts | Turn on two-factor authentication on Twitch (section 1, step 3). Unlink and link Twitch again (section 2). |
| Your friend says it stutters or freezes | Lower the quality to **720p 30 fps**. If you can, connect the PS5 to the router **with a cable**: that helps more than anything else. Avoid heavy downloads or uploads by others at home. |
| Your online game lags since you started broadcasting | Your upload is too tight. Lower the broadcast quality one step. |
| The broadcast has no game sound | Check that the game isn't muted on the PS5. If you use headphones, under **Settings** → **Sound** → **Audio Output** the game must still be playing sound (the broadcast carries the game audio). Stop the broadcast and start it again. |
| Your voice comes through with echo | Under **Broadcasts** → **Audio**, turn off the microphone and party audio (section 3). |
| A notice screen instead of the game | The game doesn't allow that scene to be broadcast. Wait until it's over. |

**Measuring the delay between you two (optional):** at a precise moment in the game, say "now!" on Discord as you press pause. Your friend times how long it takes for the pause to appear on their screen.
