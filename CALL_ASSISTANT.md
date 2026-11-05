# Call Assistant (built on Meetily)

A Windows desktop app for live calls in **any** app: Zoom, Teams, Google Meet, WhatsApp, Discord, Slack, and phone dialers.
It's assembled from open-source projects instead of being written from scratch. `THIRD_PARTY_NOTICES.md` lists them.

| Feature | Copied from | What it does |
|---|---|---|
| Real-time voice notetaker | **Meetily** (MIT), the base app | Captures your mic + the call audio, transcribes live, writes AI summaries |
| Real-time suggestions | **Realtime Interview Copilot** (Apache-2.0) | *Answer now*, *Summarize*, *Ask AI*, plus automatic "say next" tips and key notes |
| Voice changer | **OpenVoiceChanger** (MIT) | 16 live voice presets (deep, chipmunk, robot, radio, …) + pitch. No delay |
| Accent changer | **tok.si** (MIT) | You speak; the other person hears an American or British voice saying your words (~1 s delay) |
| AI voice models (optional) | **w-okada VCClient** (MIT) | Sound like a different person with RVC models (separate download) |

## How the audio flows

```
your mic ──► built-in voice engine ──► "CABLE Input" ─┐
                (effects or accent)                    │  virtual cable
call app microphone = "CABLE Output" ◄─────────────────┘
call app speaker    = your headset
```
Meetily keeps recording your real mic and the call audio, so notes and suggestions keep working while your voice is changed.

## Using it

1. **Voice & Accent** page (sidebar), first time only:
   - **Install virtual mic**: installs VB-Audio Virtual Cable. Approve the Windows prompt and restart if asked.
   - **Download voices**: about 440 MB, needed only for the accent changer.
2. In your call app, set **Microphone → CABLE Output (VB-Audio Virtual Cable)** and leave the speaker on your headset.
3. Choose what the other person hears:
   - **My real voice**: passes your mic through unchanged.
   - **Voice effects**: pick a preset and adjust the pitch.
   - **Accent changer**: pick from 8 voices (4 American, 4 British). "Balanced" timing is recommended.
     **Type to speak** says a typed sentence in the accent voice.
4. On the main screen, start recording. The **Live Copilot** panel shows tips automatically. Use:
   - **Answer now** (Ctrl+Enter): a full spoken answer to what was just asked
   - **Summarize** (Ctrl+Shift+Enter)
   - **Ask AI**: ask anything about the call
   The copilot uses the AI model chosen in **Settings → Summary model** (Claude, OpenAI, Groq, Ollama, …).

## Honest limits

- **Accent changer:** the other person hears a *different, natural English voice*, not your own voice with a new accent. No open-source model can do "your own voice with a new accent" in real time yet. Expect about 0.6–1.5 s of delay, and Whisper can occasionally mishear a word. Use a headset.
- **AI voice models** (sounding like a specific person) still need VCClient, a separate ~2 GB download that works best with an NVIDIA GPU.
- **VB-Audio Virtual Cable** is free for personal use. Check VB-Audio's licence terms before selling the app or using it across a company.
- **Web version** is not built. Browsers can't create a virtual microphone or capture other apps' audio.

## Build the Windows installer (no Windows PC needed)

1. Push this repo to a **private** GitHub repo:
   ```bash
   git remote set-url origin https://github.com/<you>/<repo>.git
   git push -u origin call-assistant
   ```
2. On GitHub, go to **Actions → "Build and Test - Windows" → Run workflow** and pick the `call-assistant` branch.
   Signing is off by default. The workflow builds the voice engine with Python and self-tests it, then builds the app installer.
3. Download the installer from the run's **Artifacts**. Unsigned builds show SmartScreen: click **More info → Run anyway**.

## Develop locally on Windows

```bat
cd voice-engine
build_windows.bat          :: builds dist\voice-engine\voice-engine.exe
cd ..\frontend
pnpm install
pnpm run tauri:dev
```
In development, if `voice-engine.exe` isn't built, the app runs `voice-engine/main.py` with your installed Python instead. Run `pip install -r voice-engine/requirements.txt` first.

## Code map

| Part | Files |
|---|---|
| Copilot (Rust) | `frontend/src-tauri/src/copilot/` (`mod.rs`, `prompts.rs`) |
| Copilot (UI) | `frontend/src/components/LiveCopilot/LiveCopilotPanel.tsx` |
| Voice engine | `voice-engine/` (`engine.py`, `dsp_effects.py`, `presets.py`, `assets.py`, `server.py`) |
| Engine launcher (Rust) | `frontend/src-tauri/src/voice_engine/mod.rs`. It starts the engine with a random token on a free localhost port and stops it on exit |
| Voice & Accent page | `frontend/src/app/voice-changer/page.tsx` |
| VCClient add-on | `frontend/src-tauri/src/voice_changer/`, `frontend/src/components/VoiceChanger/VcClientPanel.tsx` |

## Before you release
- Rename the app: `productName` and `identifier` in `frontend/src-tauri/tauri.conf.json`, plus the icons.
- Keep `THIRD_PARTY_NOTICES.md` and `voice-engine/THIRD_PARTY_NOTICES.md` in the app.
- Tell people on the call when you're recording. Don't use voice or accent changing to impersonate anyone or deceive people.
