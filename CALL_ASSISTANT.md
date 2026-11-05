# Call Assistant (built on Meetily)

This is a fork of [Meetily](https://github.com/Zackriya-Solutions/meetily) (MIT) with two features added for live calls. Everything Meetily already did still works: system-wide capture of mic + call audio on Windows, live transcription, and AI summaries.

## What was added

### 1. Live Copilot: real-time suggestions
A panel on the right of the recording screen. While you record a call, it reads the latest transcript and shows:

- **Say next**: up to 3 short things you could say. Click one to copy it.
- **Answer**: a direct answer when the other person has just asked a question.
- **Key notes**: running facts, decisions and action items, with a copy-all button.

It uses the same AI provider and model you picked in **Settings → Summary model**, whether that's Claude, OpenAI, Groq, OpenRouter, Ollama, a custom endpoint or the built-in model. No extra setup is needed. You can type context for the AI, such as who you are or the goal of the call, into the box at the top of the panel.

- Code: `frontend/src-tauri/src/copilot/mod.rs` (Tauri command `api_live_suggestions`)
- UI: `frontend/src/components/LiveCopilot/LiveCopilotPanel.tsx`
- Calls are throttled to one every 8 seconds, and fire right away when a sentence ends with "?".

### 2. Voice Changer
A new **Voice Changer** page in the sidebar. It drives the open-source [w-okada VCClient](https://github.com/w-okada/voice-changer) (MIT, RVC/Beatrice voice models) as a local engine:

- It starts and stops the engine and shows whether it's running.
- It embeds the engine's control panel, where you pick the voice model, devices and pitch.
- It walks you through setting up a virtual mic so the changed voice works in Zoom, Teams, Meet, WhatsApp or Discord:
  `real mic → VCClient → "CABLE Input"` and then `call app mic = "CABLE Output"`. This uses [VB-Audio Virtual Cable](https://vb-audio.com/Cable/).

Code: `frontend/src-tauri/src/voice_changer/mod.rs` and `frontend/src/app/voice-changer/page.tsx`

**Accent changing:** voice models change how you sound, but they keep your accent. No open-source real-time accent converter is good enough yet. The Voice Changer page is set up so a commercial accent SDK can be added later as another engine.

## Build the Windows installer (no Windows PC needed)

1. Create a new **private** repo on GitHub and push this folder to it:
   ```bash
   git remote set-url origin https://github.com/<you>/<repo>.git
   git push -u origin call-assistant
   ```
2. On GitHub, go to **Actions → "Build and Test - Windows" → Run workflow** and choose the `call-assistant` branch.
   Signing is off by default. Turn it on only after you've added your own code-signing secrets.
3. When the run finishes, download the `.exe` / `.msi` from the run's **Artifacts**.

Unsigned installers show a Windows SmartScreen warning. Click **More info → Run anyway**. For public release, buy a code-signing certificate.

## Build locally on Windows

Follow Meetily's own instructions in `README.md` and `docs/`. In short, install Rust, Node 20+, pnpm, Visual Studio Build Tools (C++), LLVM and CMake, then run:
```bat
cd frontend
pnpm install
pnpm run tauri:dev
```

## Web version: what's possible

The desktop app is the full product. A browser can't create a virtual microphone or capture other apps' audio, so in a web version:
- **Works:** notes and live suggestions for calls running in a browser tab, by sharing that tab's audio.
- **Doesn't work:** the voice changer, or capturing calls from desktop apps like WhatsApp or the Zoom app.

The web version needs its own small cloud backend for speech-to-text and the AI. Treat it as a separate next phase.

## Rules before shipping
- **Recording consent:** tell people on the call when you're recording. The laws differ by country.
- **Voices:** only use your own voice or voice models you have rights to. Don't impersonate real people.
- **License:** keep the MIT license notices from Meetily and VCClient. VCClient's voice *models* each have their own terms.
- **Name:** rename the app before release by changing `productName` and `identifier` in `frontend/src-tauri/tauri.conf.json`, and the icons in `frontend/src-tauri/icons/`.
