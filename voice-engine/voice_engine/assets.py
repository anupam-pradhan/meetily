"""Model and virtual-cable installers.

Adapted from tok.si fetch_assets.py (MIT License, Copyright (c) 2026 Andy Oliver Rozario)
https://github.com/AndyOliverR/tok.si

Changes from the original:
- the models folder is passed in (the app's data folder) instead of the script folder
- progress is reported through a callback instead of print()
- Start-menu shortcut creation and the Piper spare voices were removed
"""

import json
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

KOKORO_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-en-v0_19.tar.bz2"
WHISPER_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-tiny.en.tar.bz2"
CABLE_URL = "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack43.zip"
WHISPER_KEYS = ("whisper_encoder", "whisper_decoder", "whisper_tokens")
KOKORO_KEYS = ("kokoro_model", "kokoro_voices", "kokoro_tokens", "kokoro_data")


def _noop(_message):
    pass


def download(url, dest, min_size, timeout=180, say=_noop):
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(1, 3):
        try:
            say(f"Downloading {dest.name} (try {attempt}/2)...")
            request = urllib.request.Request(url, headers={"User-Agent": "call-assistant-voice-engine"})
            with urllib.request.urlopen(request, timeout=timeout) as response, open(dest, "wb") as handle:
                first = response.read(64)
                lowered = first.lower()
                if b"<html" in lowered or b"<!doctype" in lowered:
                    raise RuntimeError("the download was a web page, not the file")
                handle.write(first)
                while True:
                    block = response.read(1024 * 256)
                    if not block:
                        break
                    handle.write(block)
            if dest.stat().st_size < min_size:
                raise RuntimeError("the download is too small")
            return
        except Exception as exc:
            last_error = exc
            say(f"Download failed: {exc}")
            if dest.exists():
                dest.unlink()
    raise RuntimeError(last_error)


def extract_tar(archive, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:bz2") as handle:
        handle.extractall(dest, filter="data")


def first_match(root, pattern, prefer=None):
    matches = sorted(root.rglob(pattern))
    if prefer:
        ranked = [path for path in matches if prefer in path.name.lower()]
        if ranked:
            return ranked[0]
    return matches[0] if matches else None


def load_manifest(models):
    manifest = models / "manifest.json"
    if not manifest.exists():
        return {}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def paths_ready(data, keys):
    for key in keys:
        value = str(data.get(key, "")).strip()
        if not value or not Path(value).exists():
            return False
    return True


def voices_ready(models):
    data = load_manifest(models)
    return paths_ready(data, WHISPER_KEYS) and paths_ready(data, KOKORO_KEYS)


def kokoro_paths(root):
    model = first_match(root, "model.onnx")
    voices = first_match(root, "voices.bin")
    tokens = first_match(root, "tokens.txt")
    data_dirs = [path for path in root.rglob("espeak-ng-data") if path.is_dir()]
    if not model or not voices or not tokens or not data_dirs:
        raise RuntimeError(f"Kokoro voice files are incomplete in {root}")
    return model, voices, tokens, data_dirs[0]


def install_whisper(models, archive):
    whisper_root = models / "whisper"
    if whisper_root.exists():
        shutil.rmtree(whisper_root)
    extract_tar(archive, whisper_root)
    encoder = first_match(whisper_root, "*encoder*.onnx", prefer="int8")
    decoder = first_match(whisper_root, "*decoder*.onnx", prefer="int8")
    tokens = first_match(whisper_root, "*tokens.txt")
    if not encoder or not decoder or not tokens:
        raise RuntimeError("the speech model did not contain the expected files")
    return {"whisper_encoder": str(encoder), "whisper_decoder": str(decoder), "whisper_tokens": str(tokens)}


def install_kokoro(models, archive):
    voice_root = models / "kokoro"
    if voice_root.exists():
        shutil.rmtree(voice_root)
    extract_tar(archive, voice_root)
    model, voices, tokens, data_dir = kokoro_paths(voice_root)
    return {
        "kokoro_model": str(model),
        "kokoro_voices": str(voices),
        "kokoro_tokens": str(tokens),
        "kokoro_data": str(data_dir),
    }


def ensure_voices(models, say=_noop):
    """Download Whisper tiny.en (speech-to-text) and Kokoro (accent voices)."""
    models.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(models)
    if paths_ready(manifest, WHISPER_KEYS) and paths_ready(manifest, KOKORO_KEYS):
        say("Voice files are already in place.")
        return manifest
    cache = models / "_downloads"
    cache.mkdir(parents=True, exist_ok=True)
    if not paths_ready(manifest, WHISPER_KEYS):
        archive = cache / "whisper.tar.bz2"
        download(WHISPER_URL, archive, 50_000_000, say=say)
        say("Unpacking speech model...")
        manifest.update(install_whisper(models, archive))
        archive.unlink(missing_ok=True)
    if not paths_ready(manifest, KOKORO_KEYS):
        archive = cache / "kokoro-en-v0_19.tar.bz2"
        download(KOKORO_URL, archive, 50_000_000, timeout=600, say=say)
        say("Unpacking accent voices...")
        manifest.update(install_kokoro(models, archive))
        archive.unlink(missing_ok=True)
    (models / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    say("Voice files are ready.")
    return manifest


def cable_present():
    import sounddevice as sd

    for dev in sd.query_devices():
        name = str(dev["name"]).upper()
        if dev["max_output_channels"] > 0 and "CABLE INPUT" in name:
            return True
    return False


def ensure_cable(work_dir, say=_noop):
    """Download and run the VB-Audio Virtual Cable installer (Windows)."""
    if cable_present():
        say("Virtual cable is already installed.")
        return True
    cable_dir = work_dir / "vbcable"
    exe = cable_dir / "VBCABLE_Setup_x64.exe"
    if not exe.exists():
        archive = work_dir / "_vbcable_pack.zip"
        download(CABLE_URL, archive, 500_000, say=say)
        if cable_dir.exists():
            shutil.rmtree(cable_dir)
        cable_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(cable_dir)
        archive.unlink(missing_ok=True)
    if not exe.exists():
        raise RuntimeError("the virtual cable installer was not in the download")
    say("Approve the virtual cable installer window, then click Install Driver.")
    subprocess.call([str(exe)])
    if not cable_present():
        raise RuntimeError(
            "The virtual cable is not available yet. If you approved the installer, restart the PC and open the app again."
        )
    say("Virtual cable is ready.")
    return True
