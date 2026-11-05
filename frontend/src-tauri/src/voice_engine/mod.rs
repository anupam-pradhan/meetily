//! Built-in voice engine (voice effects + real-time accent changer).
//!
//! The engine is a small bundled program (`voice-engine/` at the repo root,
//! packaged as `voice-engine.exe` with PyInstaller) built from:
//!   - tok.si (MIT) – mic → CABLE Input stream, phrase cutting, Whisper + Kokoro accent voice
//!   - OpenVoiceChanger (MIT) – pitch/formant shifting, effect rack and 16 voice presets
//!
//! This module starts it on demand, gives it a random per-launch token and a
//! free localhost port, forwards the UI's requests to it, and stops it on exit.

use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Manager, Runtime};

struct EngineProcess {
    child: Child,
    port: u16,
    token: String,
}

static ENGINE: Mutex<Option<EngineProcess>> = Mutex::new(None);

/// Requests the UI may forward. Anything else is rejected.
const ALLOWED: &[(&str, &str)] = &[
    ("GET", "/status"),
    ("GET", "/devices"),
    ("GET", "/options"),
    ("POST", "/config"),
    ("POST", "/setup"),
    ("POST", "/say"),
];

fn free_port() -> Result<u16, String> {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    Ok(listener.local_addr().map_err(|e| e.to_string())?.port())
}

fn new_token() -> String {
    format!("{}{}", uuid::Uuid::new_v4().simple(), uuid::Uuid::new_v4().simple())
}

/// Where the engine lives:
/// 1. bundled: <resources>/voice-engine/voice-engine(.exe)
/// 2. development: run `python voice-engine/main.py` from the repo
fn engine_command<R: Runtime>(app: &AppHandle<R>) -> Result<Command, String> {
    let exe_name = if cfg!(windows) { "voice-engine.exe" } else { "voice-engine" };
    if let Ok(resources) = app.path().resource_dir() {
        let bundled = resources.join("voice-engine").join(exe_name);
        if bundled.is_file() {
            let mut cmd = Command::new(&bundled);
            if let Some(dir) = bundled.parent() {
                cmd.current_dir(dir);
            }
            return Ok(cmd);
        }
    }

    // Development fallback: repo-root/voice-engine/main.py
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let script = manifest_dir.join("../../voice-engine/main.py");
    if script.is_file() {
        let python = std::env::var("VOICE_ENGINE_PYTHON")
            .unwrap_or_else(|_| if cfg!(windows) { "python".into() } else { "python3".into() });
        let mut cmd = Command::new(python);
        cmd.arg(&script);
        if let Some(dir) = script.parent() {
            cmd.current_dir(dir);
        }
        return Ok(cmd);
    }
    Err("The voice engine is not installed with this build.".into())
}

fn data_dir<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?
        .join("voice-engine");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir)
}

fn running() -> Option<(u16, String)> {
    let mut guard = ENGINE.lock().ok()?;
    let alive = match guard.as_mut() {
        Some(p) => matches!(p.child.try_wait(), Ok(None)),
        None => false,
    };
    if !alive {
        *guard = None;
        return None;
    }
    guard.as_ref().map(|p| (p.port, p.token.clone()))
}

fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(20))
        .no_proxy()
        .build()
        .map_err(|e| e.to_string())
}

async fn call(port: u16, token: &str, method: &str, path: &str, body: Option<Value>) -> Result<Value, String> {
    let url = format!("http://127.0.0.1:{port}{path}");
    let c = client()?;
    let req = match method {
        "GET" => c.get(&url),
        _ => c.post(&url).json(&body.unwrap_or(Value::Object(Default::default()))),
    };
    let resp = req
        .header("X-Engine-Token", token)
        .send()
        .await
        .map_err(|e| format!("Voice engine not reachable: {e}"))?;
    let status = resp.status();
    let value: Value = resp.json().await.unwrap_or(Value::Null);
    if status.is_success() {
        Ok(value)
    } else {
        Err(value
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("voice engine error")
            .to_string())
    }
}

/// Start the engine if needed and wait until it answers.
#[tauri::command]
pub async fn voice_engine_ensure<R: Runtime>(app: AppHandle<R>) -> Result<Value, String> {
    if let Some((port, token)) = running() {
        if let Ok(v) = call(port, &token, "GET", "/status", None).await {
            return Ok(v);
        }
    }

    let port = free_port()?;
    let token = new_token();
    let data = data_dir(&app)?;
    let mut cmd = engine_command(&app)?;
    cmd.arg("--port")
        .arg(port.to_string())
        .arg("--data-dir")
        .arg(&data)
        .env("VOICE_ENGINE_TOKEN", &token)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let child = cmd.spawn().map_err(|e| format!("Could not start the voice engine: {e}"))?;
    {
        let mut guard = ENGINE.lock().map_err(|_| "engine lock poisoned")?;
        if let Some(mut old) = guard.take() {
            let _ = old.child.kill();
        }
        *guard = Some(EngineProcess { child, port, token: token.clone() });
    }

    // First start of a PyInstaller build can take a few seconds.
    for _ in 0..60 {
        tokio::time::sleep(Duration::from_millis(500)).await;
        if running().is_none() {
            return Err(format!(
                "The voice engine stopped while starting. See {}",
                data.join("voice-engine.log").display()
            ));
        }
        if let Ok(v) = call(port, &token, "GET", "/status", None).await {
            log::info!("voice engine ready on port {port}");
            return Ok(v);
        }
    }
    Err("The voice engine did not start in time.".into())
}

/// Forward one request from the Voice Changer page to the engine.
#[tauri::command]
pub async fn voice_engine_request(method: String, path: String, body: Option<Value>) -> Result<Value, String> {
    let method = method.to_ascii_uppercase();
    if !ALLOWED.iter().any(|(m, p)| *m == method && *p == path) {
        return Err(format!("{method} {path} is not allowed"));
    }
    let (port, token) = running().ok_or("The voice engine is not running.")?;
    call(port, &token, &method, &path, body).await
}

/// Stop the engine (also called on app exit).
pub fn shutdown_engine() {
    let taken = ENGINE.lock().ok().and_then(|mut g| g.take());
    if let Some(mut p) = taken {
        // Ask politely so the audio stream closes cleanly, then make sure.
        let url = format!("http://127.0.0.1:{}/shutdown", p.port);
        let _ = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(2))
            .no_proxy()
            .build()
            .and_then(|c| c.post(&url).header("X-Engine-Token", &p.token).send());
        std::thread::sleep(Duration::from_millis(300));
        let _ = p.child.kill();
        let _ = p.child.wait();
    }
}

#[tauri::command]
pub async fn voice_engine_stop() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(shutdown_engine)
        .await
        .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn token_is_long_and_unique() {
        let a = new_token();
        let b = new_token();
        assert_eq!(a.len(), 64);
        assert_ne!(a, b);
    }

    #[test]
    fn only_allowlisted_paths() {
        let rt = tokio::runtime::Runtime::new().unwrap();
        let err = rt
            .block_on(voice_engine_request("POST".into(), "/shutdown".into(), None))
            .unwrap_err();
        assert!(err.contains("not allowed"));
    }

    #[test]
    fn free_port_is_nonzero() {
        assert!(free_port().unwrap() > 0);
    }
}
