@echo off
REM Builds the voice engine into dist\voice-engine\voice-engine.exe (run on Windows).
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python -m PyInstaller --noconfirm --clean --console --onedir --name voice-engine ^
  --exclude-module pkg_resources --exclude-module setuptools ^
  --collect-all sherpa_onnx --collect-all sounddevice --collect-submodules scipy.signal ^
  main.py || exit /b 1
dist\voice-engine\voice-engine.exe --self-test || exit /b 1
echo Built dist\voice-engine\voice-engine.exe
