"""Offline tests for the voice engine (no audio devices or model downloads needed).

Run: python -m pytest voice-engine/tests   (from the repo root)
"""

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice_engine.dsp_effects import EffectsChain  # noqa: E402
from voice_engine.engine import ACCENT_VOICES, STREAM_RATE, VoiceEngine, resample  # noqa: E402
from voice_engine.presets import BUILTIN_PRESETS  # noqa: E402
from voice_engine.server import make_handler  # noqa: E402


def tone(seconds=0.5, hz=220):
    t = np.arange(int(STREAM_RATE * seconds)) / STREAM_RATE
    return (0.2 * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def test_every_preset_keeps_block_size():
    chain = EffectsChain(STREAM_RATE)
    x = tone()
    for preset in BUILTIN_PRESETS:
        s = preset["settings"]
        y = chain.post_process(chain.apply_pitch(x, s["pitch_shift"]), s["effects"], s["formant_shift"])
        assert y.shape == x.shape and np.all(np.abs(y) <= 1.0), preset["id"]


def test_voice_mode_changes_audio_and_off_passes_through(tmp_path):
    e = VoiceEngine(tmp_path, log=lambda m: None)
    block = tone(1024 / STREAM_RATE)
    assert np.array_equal(e.process_block(block), block)  # off
    e.update_config({"mode": "voice", "preset": "deep"})
    out = np.concatenate([e.process_block(tone(1024 / STREAM_RATE)) for _ in range(20)])
    assert out.shape == (20 * 1024,)
    assert not np.allclose(out[-1024:], block)


def test_config_validation(tmp_path):
    e = VoiceEngine(tmp_path, log=lambda m: None)
    with pytest.raises(ValueError):
        e.update_config({"mode": "nope"})
    with pytest.raises(ValueError):
        e.update_config({"accent_voice": "fr_male"})
    cfg = e.update_config({"pitch": 99, "accent_speed": 9, "unknown": 1})
    assert cfg["pitch"] == 12.0 and cfg["accent_speed"] == 1.4 and "unknown" not in cfg


def test_accent_voices_are_distinct_kokoro_ids():
    sids = [v["sid"] for v in ACCENT_VOICES.values()]
    assert len(sids) == len(set(sids)) and all(0 <= s <= 10 for s in sids)


def test_playback_buffer_and_resample(tmp_path):
    e = VoiceEngine(tmp_path, log=lambda m: None)
    e.enqueue_audio(np.ones(1500, np.float32))
    a = e.pull_audio(1024)
    b = e.pull_audio(1024)
    assert a.sum() == 1024 and b[:476].sum() == 476 and b[476:].sum() == 0
    assert len(resample(np.zeros(24000, np.float32), 24000, STREAM_RATE)) == STREAM_RATE


def test_api_requires_token(tmp_path):
    from http.server import ThreadingHTTPServer

    e = VoiceEngine(tmp_path, log=lambda m: None)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(e, "secret-token-123456", lambda: None))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(url + "/options", timeout=5)
        assert err.value.code == 401
        req = urllib.request.Request(url + "/options", headers={"X-Engine-Token": "secret-token-123456"})
        data = json.load(urllib.request.urlopen(req, timeout=5))
        assert len(data["presets"]) == 16 and len(data["accent_voices"]) == 8
        req = urllib.request.Request(
            url + "/config",
            data=json.dumps({"mode": "voice", "preset": "robot"}).encode(),
            headers={"X-Engine-Token": "secret-token-123456"},
            method="POST",
        )
        assert json.load(urllib.request.urlopen(req, timeout=5))["config"]["preset"] == "robot"
    finally:
        httpd.shutdown()
