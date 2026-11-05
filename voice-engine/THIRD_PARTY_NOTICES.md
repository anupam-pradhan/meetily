# Third-party notices: voice engine

This engine is assembled from the following open-source projects.

| Project | Used for | License | Source (commit) |
|---|---|---|---|
| tok.si by Andy Oliver Rozario | Mic → CABLE Input stream, phrase cutting, Whisper + Kokoro accent pipeline, model and VB-Cable installers (`engine.py`, `assets.py`) | MIT | https://github.com/AndyOliverR/tok.si (0c7066f) |
| OpenVoiceChanger by Sioaeko | Pitch/formant shifting, effect rack, 16 voice presets (`dsp_effects.py`, `presets.py`) | MIT | https://github.com/sioaeko/OpenVoiceChanger (8e6a00c) |
| sherpa-onnx (k2-fsa) | Runs Whisper and Kokoro on the CPU | Apache-2.0 | https://github.com/k2-fsa/sherpa-onnx |
| Whisper tiny.en (OpenAI) | Speech-to-text model, downloaded on first use | MIT | https://github.com/openai/whisper |
| Kokoro-82M v0.19 (hexgrad) | Accent voices, downloaded on first use | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M |
| VB-Audio Virtual Cable | Virtual microphone; downloaded from VB-Audio and installed only after the user approves | Donationware; not redistributed here | https://vb-audio.com/Cable/ |

---

## tok.si: MIT License

MIT License

Copyright (c) 2026 Andy Oliver Rozario

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## OpenVoiceChanger: MIT License

MIT License

Copyright (c) 2024 Sioaeko

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
