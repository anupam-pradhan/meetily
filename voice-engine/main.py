"""Voice engine entry point (started by the desktop app).

Usage: voice-engine --port 47700 --data-dir <folder>
The access token is read from the VOICE_ENGINE_TOKEN environment variable.
"""

import argparse
import os
import sys
import time
from pathlib import Path

from voice_engine.engine import VoiceEngine
from voice_engine.server import serve


def main():
    parser = argparse.ArgumentParser(description="Real-time voice and accent engine")
    parser.add_argument("--port", type=int, default=47700)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--self-test", action="store_true", help="check bundled libraries load, then exit")
    args = parser.parse_args()

    if args.self_test:
        import numpy
        import scipy
        import sherpa_onnx
        from voice_engine.dsp_effects import EffectsChain
        from voice_engine.presets import BUILTIN_PRESETS

        EffectsChain(48000)
        try:
            import sounddevice

            audio = f"sounddevice {sounddevice.__version__}, {len(sounddevice.query_devices())} devices"
        except OSError as exc:  # no audio stack (e.g. headless CI)
            audio = f"sounddevice unavailable: {exc}"
        print(f"self-test ok: numpy {numpy.__version__}, scipy {scipy.__version__}, "
              f"sherpa-onnx {sherpa_onnx.__version__}, {len(BUILTIN_PRESETS)} presets, {audio}")
        return 0
    if args.data_dir is None:
        parser.error("--data-dir is required")

    token = os.environ.get("VOICE_ENGINE_TOKEN", "")
    if len(token) < 16:
        print("VOICE_ENGINE_TOKEN missing or too short", file=sys.stderr)
        return 2

    args.data_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.data_dir / "voice-engine.log"

    def log(message):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
        print(line, flush=True)
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    engine = VoiceEngine(args.data_dir, log=log)
    log(f"voice engine listening on 127.0.0.1:{args.port}")
    serve(engine, args.port, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
