"""Real-time voice + accent engine.

Microphone in -> processing -> "CABLE Input" out. Call apps pick "CABLE Output"
as their microphone, so the other person hears the processed voice.

The audio stream, phrase cutting, Whisper transcription and Kokoro speech are
adapted from tok.si main.py (MIT License, Copyright (c) 2026 Andy Oliver Rozario,
https://github.com/AndyOliverR/tok.si): `resolve_devices`, `ensure_stream`'s
callback, `enqueue_audio`/`pull_audio`, `engine_loop`, `transcribe`,
`speak_kokoro` and `resample`. The Qt window, updater and wizard were removed
and the voice-effects mode was added.

Voice effects (pitch, formant, effect rack, 16 presets) come from
OpenVoiceChanger (MIT License, Copyright (c) 2024 Sioaeko):
see dsp_effects.py and presets.py.

Modes
  off     - your real microphone passes straight through
  voice   - live voice effects / presets on your own voice (no delay)
  accent  - you speak, the line is re-spoken in the chosen English accent
            (~1 s delay). Optional preset can be applied on top.
"""

import queue
import threading
import time
from pathlib import Path

import numpy as np

from . import assets
from .dsp_effects import EffectsChain
from .presets import PRESETS_BY_ID

STREAM_RATE = 48000
BLOCK = 1024
SILENCE_SECONDS = 0.2
SPEECH_SECONDS = 1.0
LEVEL_GATE = 0.015
HEADSET_WORDS = ("HEADSET", "HEADPHONE", "AIRPOD", "BLUETOOTH", "BUDS", "EARBUD", "HANDS-FREE")
SKIP_TEXT = {
    "thanks for watching",
    "thank you for watching",
    "thanks for watching.",
    "subscribe",
    "you",
    "...",
    ".",
}

# Kokoro en v0.19 speaker ids (sherpa-onnx kokoro-en-v0_19, voices.bin order):
# 0 af, 1 af_bella, 2 af_nicole, 3 af_sarah, 4 af_sky, 5 am_adam,
# 6 am_michael, 7 bf_emma, 8 bf_isabella, 9 bm_george, 10 bm_lewis
ACCENT_VOICES = {
    "us_female": {"sid": 3, "label": "American - female (Sarah)"},
    "us_male": {"sid": 6, "label": "American - male (Michael)"},
    "us_female_2": {"sid": 1, "label": "American - female (Bella)"},
    "us_male_2": {"sid": 5, "label": "American - male (Adam)"},
    "uk_female": {"sid": 7, "label": "British - female (Emma)"},
    "uk_male": {"sid": 9, "label": "British - male (George)"},
    "uk_female_2": {"sid": 8, "label": "British - female (Isabella)"},
    "uk_male_2": {"sid": 10, "label": "British - male (Lewis)"},
}
MODES = ("off", "voice", "accent")
ACCENT_WAIT_SECONDS = {"fast": SPEECH_SECONDS, "balanced": 2.0, "smooth": 3.5}


def resample(audio, src, dst):
    count = int(len(audio) * dst / src)
    if count < 1:
        return np.zeros(0, dtype=np.float32)
    old = np.linspace(0.0, 1.0, len(audio), endpoint=False)
    new = np.linspace(0.0, 1.0, count, endpoint=False)
    return np.interp(new, old, audio).astype(np.float32)


class VoiceEngine:
    def __init__(self, data_dir: Path, log=print):
        self.data_dir = Path(data_dir)
        self.models_dir = self.data_dir / "models"
        self.log = log

        self.config = {
            "mode": "off",
            "preset": "clean",
            "pitch": 0.0,  # extra semitones on top of the preset
            "accent_voice": "us_female",
            "accent_speed": 1.0,
            # how long you may talk before a line is sent anyway:
            # fast = 1 s (tok.si default, may split words), balanced = 2 s, smooth = 3.5 s
            "accent_wait": "balanced",
            "accent_preset": "clean",  # effects applied to the accent voice
            "mic_device": None,  # name override; None = auto (headset first)
            "cable_device": None,  # name override; None = "CABLE Input"
        }
        self.cfg_lock = threading.Lock()

        self.stream = None
        self.device_key = None
        self.devices_ok = False
        self.stream_error = None

        self.play_lock = threading.Lock()
        self.play_buf = np.zeros(0, dtype=np.float32)
        self.input_queue = queue.Queue(maxsize=400)
        self.stop_event = threading.Event()

        self.voice_chain = EffectsChain(STREAM_RATE)
        self.accent_chain = EffectsChain(STREAM_RATE)

        self.recognizer = None
        self.tts = None
        self.models_lock = threading.Lock()
        self.models_error = None

        self.levels_in = 0.0
        self.levels_out = 0.0
        self.last_text = ""
        self.last_latency_ms = None
        self.phrases = 0
        self.setup_task = None
        self.setup_messages = []
        self.setup_error = None

        self.engine_thread = threading.Thread(target=self.engine_loop, daemon=True)
        self.watch_thread = threading.Thread(target=self.watch_loop, daemon=True)

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        self.engine_thread.start()
        self.watch_thread.start()

    def shutdown(self):
        self.stop_event.set()
        self.stop_stream()

    # ------------------------------------------------------------------ config
    def update_config(self, changes: dict):
        with self.cfg_lock:
            for key, value in changes.items():
                if key not in self.config:
                    continue
                if key == "mode" and value not in MODES:
                    raise ValueError(f"mode must be one of {MODES}")
                if key in ("preset", "accent_preset") and value not in PRESETS_BY_ID:
                    raise ValueError(f"unknown preset {value!r}")
                if key == "accent_wait" and value not in ACCENT_WAIT_SECONDS:
                    raise ValueError(f"accent_wait must be one of {tuple(ACCENT_WAIT_SECONDS)}")
                if key == "accent_voice" and value not in ACCENT_VOICES:
                    raise ValueError(f"unknown accent voice {value!r}")
                if key == "pitch":
                    value = float(max(-12.0, min(12.0, float(value))))
                if key == "accent_speed":
                    value = float(max(0.7, min(1.4, float(value))))
                self.config[key] = value
            mode = self.config["mode"]
            devices_changed = "mic_device" in changes or "cable_device" in changes
        if devices_changed:
            self.device_key = None
        if mode == "accent":
            threading.Thread(target=self.load_models, daemon=True).start()
        self.clear_playback()
        return dict(self.config)

    def snapshot_config(self):
        with self.cfg_lock:
            return dict(self.config)

    # ------------------------------------------------------------------ devices (tok.si)
    def list_devices(self):
        import sounddevice as sd

        out = {"inputs": [], "outputs": []}
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
        except Exception as exc:
            return {"inputs": [], "outputs": [], "error": str(exc)}
        for dev in devices:
            api = str(hostapis[dev["hostapi"]]["name"])
            item = {"name": str(dev["name"]), "api": api}
            if dev["max_input_channels"] > 0:
                out["inputs"].append(item)
            if dev["max_output_channels"] > 0:
                out["outputs"].append(item)
        return out

    def resolve_devices(self):
        import sounddevice as sd

        cfg = self.snapshot_config()
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
        except Exception as exc:
            self.log(f"device query failed: {exc}")
            return None, None
        wasapi = None
        for index, host in enumerate(hostapis):
            if "WASAPI" in str(host["name"]).upper():
                wasapi = index
                break
        mic = None
        headset = None
        cable = None
        want_mic = (cfg["mic_device"] or "").upper()
        want_cable = (cfg["cable_device"] or "CABLE INPUT").upper()
        for index, dev in enumerate(devices):
            name = str(dev["name"]).upper()
            if wasapi is not None and dev["hostapi"] != wasapi:
                continue
            if dev["max_input_channels"] > 0 and "CABLE" not in name:
                if want_mic and want_mic in name and mic is None:
                    mic = index
                    headset = index
                if any(word in name for word in HEADSET_WORDS):
                    headset = headset if headset is not None else index
                mic = mic if mic is not None else index
            if dev["max_output_channels"] > 0 and want_cable in name and cable is None:
                cable = index
        if cable is None:
            for index, dev in enumerate(devices):
                name = str(dev["name"]).upper()
                if dev["max_output_channels"] > 0 and want_cable in name:
                    cable = index
                    break
        chosen = headset if headset is not None else mic
        return chosen, cable

    # ------------------------------------------------------------------ playback buffer (tok.si)
    def clear_playback(self):
        with self.play_lock:
            self.play_buf = np.zeros(0, dtype=np.float32)

    def enqueue_audio(self, samples):
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        samples = np.clip(samples, -1.0, 1.0)
        with self.play_lock:
            self.play_buf = np.concatenate([self.play_buf, samples])
            limit = STREAM_RATE * 6
            if len(self.play_buf) > limit:
                self.play_buf = self.play_buf[-limit:]

    def pull_audio(self, count):
        with self.play_lock:
            if len(self.play_buf) >= count:
                out = self.play_buf[:count].copy()
                self.play_buf = self.play_buf[count:]
                return out
            out = np.zeros(count, dtype=np.float32)
            have = len(self.play_buf)
            if have:
                out[:have] = self.play_buf
                self.play_buf = np.zeros(0, dtype=np.float32)
            return out

    # ------------------------------------------------------------------ audio stream
    def process_block(self, raw):
        """Called from the audio callback for every block. Must stay cheap."""
        cfg = self.config  # read without lock; values are replaced atomically
        mode = cfg["mode"]
        if mode == "voice":
            preset = PRESETS_BY_ID.get(cfg["preset"], PRESETS_BY_ID["clean"])["settings"]
            semis = float(preset.get("pitch_shift", 0)) + float(cfg["pitch"])
            y = raw
            y = self.voice_chain.pre_process(y, preset.get("effects", {}))
            if abs(semis) > 1e-3:
                y = self.voice_chain.apply_pitch(y, semis)
            return self.voice_chain.post_process(y, preset.get("effects", {}), float(preset.get("formant_shift", 0)))
        if mode == "accent" and self.recognizer is not None and self.tts is not None:
            try:
                self.input_queue.put_nowait(raw.copy())
            except queue.Full:
                pass
            return self.pull_audio(len(raw))
        return raw

    def ensure_stream(self):
        import sounddevice as sd

        mic, cable = self.resolve_devices()
        if mic is None or cable is None:
            if self.devices_ok:
                self.log("link disconnected: mic or CABLE Input missing")
            self.devices_ok = False
            self.stop_stream()
            self.device_key = None
            return
        self.devices_ok = True
        key = (mic, cable)
        if self.stream is not None and self.device_key == key:
            return
        self.stop_stream()
        self.device_key = key

        def audio_callback(indata, outdata, frames, time_info, status):
            try:
                raw = np.asarray(indata[:, 0], dtype=np.float32)
                self.levels_in = float(np.max(np.abs(raw))) if len(raw) else 0.0
                try:
                    out = self.process_block(raw)
                except Exception:
                    out = raw
                if len(out) != frames:
                    fixed = np.zeros(frames, dtype=np.float32)
                    fixed[: min(frames, len(out))] = out[:frames]
                    out = fixed
                outdata[:, 0] = out
                self.levels_out = float(np.max(np.abs(out))) if len(out) else 0.0
            except Exception:
                outdata.fill(0)

        try:
            self.stream = sd.Stream(
                device=(mic, cable),
                samplerate=STREAM_RATE,
                blocksize=BLOCK,
                channels=1,
                dtype="float32",
                callback=audio_callback,
            )
            self.stream.start()
            self.stream_error = None
            self.log(f"stream live: mic={mic} cable={cable}")
        except Exception as exc:
            self.log(f"stream start failed: {exc}")
            self.stream_error = str(exc)
            self.stream = None
            self.device_key = None

    def stop_stream(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as exc:
                self.log(f"stream stop failed: {exc}")
            self.stream = None

    def watch_loop(self):
        """Re-check devices every 2 s so a plugged headset or new cable is picked up."""
        while not self.stop_event.is_set():
            try:
                self.ensure_stream()
            except Exception as exc:
                self.log(f"device watch failed: {exc}")
            self.stop_event.wait(2.0)

    # ------------------------------------------------------------------ models (tok.si)
    def load_models(self):
        with self.models_lock:
            if self.recognizer is not None and self.tts is not None:
                return True
            manifest = assets.load_manifest(self.models_dir)
            if not (assets.paths_ready(manifest, assets.WHISPER_KEYS) and assets.paths_ready(manifest, assets.KOKORO_KEYS)):
                self.models_error = "Accent voices are not installed yet. Run setup first."
                return False
            try:
                import sherpa_onnx

                if self.recognizer is None:
                    self.recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                        encoder=manifest["whisper_encoder"],
                        decoder=manifest["whisper_decoder"],
                        tokens=manifest["whisper_tokens"],
                        language="en",
                        task="transcribe",
                        num_threads=2,
                    )
                    self.log("whisper ready")
                if self.tts is None:
                    config = sherpa_onnx.OfflineTtsConfig(
                        model=sherpa_onnx.OfflineTtsModelConfig(
                            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                                model=manifest["kokoro_model"],
                                voices=manifest["kokoro_voices"],
                                tokens=manifest["kokoro_tokens"],
                                data_dir=manifest["kokoro_data"],
                            ),
                            num_threads=2,
                            provider="cpu",
                        ),
                        max_num_sentences=1,
                    )
                    if not config.validate():
                        raise RuntimeError("voice file is not valid")
                    self.tts = sherpa_onnx.OfflineTts(config)
                    self.log("kokoro ready")
                self.models_error = None
                return True
            except Exception as exc:
                self.models_error = f"Could not load accent voices: {exc}"
                self.log(self.models_error)
                return False

    def transcribe(self, audio):
        stream = self.recognizer.create_stream()
        stream.accept_waveform(STREAM_RATE, np.asarray(audio, dtype=np.float32))
        self.recognizer.decode_stream(stream)
        return stream.result.text.strip()

    def speak(self, text):
        cfg = self.snapshot_config()
        sid = ACCENT_VOICES.get(cfg["accent_voice"], ACCENT_VOICES["us_female"])["sid"]
        audio = self.tts.generate(text, sid=sid, speed=float(cfg["accent_speed"]))
        samples = np.asarray(audio.samples, dtype=np.float32)
        rate = int(audio.sample_rate)
        if rate != STREAM_RATE and len(samples):
            samples = resample(samples, rate, STREAM_RATE)
        preset = PRESETS_BY_ID.get(cfg["accent_preset"], PRESETS_BY_ID["clean"])["settings"]
        if preset.get("effects") or preset.get("pitch_shift") or preset.get("formant_shift"):
            if preset.get("pitch_shift"):
                samples = self.accent_chain.apply_pitch(samples, float(preset["pitch_shift"]))
            samples = self.accent_chain.post_process(samples, preset.get("effects", {}), float(preset.get("formant_shift", 0)))
        return samples

    def say(self, text):
        """Speak typed text into the call in the accent voice."""
        text = (text or "").strip()
        if not text:
            return False
        if not self.load_models():
            raise RuntimeError(self.models_error or "accent voices not ready")
        samples = self.speak(text)
        self.enqueue_audio(samples)
        self.last_text = text[:200]
        return True

    def engine_loop(self):
        """Cut phrases on a 0.2 s pause or after the chosen speech length (tok.si timing)."""
        pending = []
        voiced = 0
        silent = 0
        in_speech = False
        silence_need = int(SILENCE_SECONDS * STREAM_RATE)
        speech_need = int(SPEECH_SECONDS * STREAM_RATE)
        while not self.stop_event.is_set():
            try:
                piece = self.input_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if self.config["mode"] != "accent" or self.recognizer is None or self.tts is None:
                pending = []
                in_speech = False
                voiced = 0
                silent = 0
                continue
            pending.append(piece)
            level = float(np.sqrt(np.mean(np.square(piece)))) if len(piece) else 0.0
            if level >= LEVEL_GATE:
                in_speech = True
                voiced += len(piece)
                silent = 0
            elif in_speech:
                silent += len(piece)
            else:
                total = sum(len(part) for part in pending)
                if total > STREAM_RATE:
                    pending = pending[-1:]
                continue
            speech_need = int(ACCENT_WAIT_SECONDS.get(self.config["accent_wait"], SPEECH_SECONDS) * STREAM_RATE)
            if voiced < speech_need and silent < silence_need:
                continue
            audio = np.concatenate(pending)
            pending = []
            in_speech = False
            voiced = 0
            silent = 0
            if len(audio) < int(0.25 * STREAM_RATE):
                continue
            try:
                started = time.perf_counter()
                text = self.transcribe(audio)
                if not text or text.lower().strip(" .") in SKIP_TEXT:
                    continue
                samples = self.speak(text)
                if len(samples):
                    self.enqueue_audio(samples)
                self.last_latency_ms = int((time.perf_counter() - started) * 1000)
                self.last_text = text[:200]
                self.phrases += 1
            except Exception as exc:
                self.log(f"voice step failed: {exc}")

    # ------------------------------------------------------------------ setup
    def _run_setup(self, name, fn):
        self.setup_task = name
        self.setup_error = None
        self.setup_messages = []

        def say(message):
            self.setup_messages = (self.setup_messages + [message])[-20:]
            self.log(message)

        try:
            fn(say)
        except Exception as exc:
            self.setup_error = str(exc)
            say(f"Setup stopped: {exc}")
        finally:
            self.setup_task = None

    def start_setup(self, what):
        if self.setup_task:
            raise RuntimeError(f"{self.setup_task} setup is already running")
        if what == "voices":
            fn = lambda say: (assets.ensure_voices(self.models_dir, say=say), self.load_models())
        elif what == "cable":
            fn = lambda say: (assets.ensure_cable(self.data_dir, say=say), setattr(self, "device_key", None))
        else:
            raise ValueError("setup must be 'voices' or 'cable'")
        threading.Thread(target=self._run_setup, args=(what, fn), daemon=True).start()

    # ------------------------------------------------------------------ status
    def status(self):
        try:
            cable = assets.cable_present()
        except Exception:
            cable = False
        return {
            "config": self.snapshot_config(),
            "stream_live": self.stream is not None,
            "devices_ok": self.devices_ok,
            "cable_installed": cable,
            "stream_error": self.stream_error,
            "voices_installed": assets.voices_ready(self.models_dir),
            "accent_ready": self.recognizer is not None and self.tts is not None,
            "models_error": self.models_error,
            "level_in": round(self.levels_in, 3),
            "level_out": round(self.levels_out, 3),
            "last_text": self.last_text,
            "last_latency_ms": self.last_latency_ms,
            "phrases": self.phrases,
            "setup_task": self.setup_task,
            "setup_messages": self.setup_messages[-6:],
            "setup_error": self.setup_error,
        }
