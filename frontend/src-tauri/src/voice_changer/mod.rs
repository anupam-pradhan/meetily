//! Voice changer integration.
//!
//! Instead of re-implementing real-time voice conversion, this app drives the
//! open-source w-okada VCClient (MIT, RVC/Beatrice models) as a local engine.
//! VCClient serves its own control UI and API on http://127.0.0.1:18888.
//! Its output is routed to a virtual microphone (e.g. VB-Audio "CABLE Input"),
//! which the user then selects as the mic in Zoom / Teams / WhatsApp / Meet.

use serde::Serialize;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Duration;

static ENGINE: Mutex<Option<std::process::Child>> = Mutex::new(None);

#[derive(Debug, Serialize)]
pub struct VoiceEngineStatus {
    pub reachable: bool,
    pub launched_by_app: bool,
    pub url: String,
}

fn normalise_url(url: Option<String>) -> String {
    url.map(|u| u.trim().trim_end_matches('/').to_string())
        .filter(|u| !u.is_empty())
        .unwrap_or_else(|| "http://127.0.0.1:18888".to_string())
}

fn is_local(url: &str) -> bool {
    let rest = url
        .strip_prefix("http://")
        .or_else(|| url.strip_prefix("https://"))
        .unwrap_or("");
    rest.starts_with("127.0.0.1") || rest.starts_with("localhost")
}

/// Check whether the VCClient engine is running and reachable.
#[tauri::command]
pub async fn voice_engine_status(url: Option<String>) -> Result<VoiceEngineStatus, String> {
    let url = normalise_url(url);
    if !is_local(&url) {
        return Err("The voice engine must run on this computer (127.0.0.1 or localhost).".into());
    }
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        // VCClient may use a self-signed cert when started in https mode.
        .danger_accept_invalid_certs(true)
        .build()
        .map_err(|e| e.to_string())?;
    let reachable = client.get(&url).send().await.is_ok();

    let launched_by_app = {
        let mut guard = ENGINE.lock().map_err(|_| "engine lock poisoned")?;
        match guard.as_mut() {
            Some(child) => match child.try_wait() {
                Ok(None) => true,
                _ => {
                    *guard = None;
                    false
                }
            },
            None => false,
        }
    };

    Ok(VoiceEngineStatus { reachable, launched_by_app, url })
}

/// Launch VCClient from the path the user selected (e.g. C:\\vcclient\\start_http.bat
/// or the bundled .exe).
#[tauri::command]
pub async fn voice_engine_start(path: String) -> Result<(), String> {
    let path = PathBuf::from(path.trim());
    if !path.is_file() {
        return Err(format!("File not found: {}", path.display()));
    }
    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_ascii_lowercase())
        .unwrap_or_default();
    if !matches!(ext.as_str(), "exe" | "bat" | "cmd" | "sh" | "") {
        return Err("Pick the VCClient .exe or start_http.bat file.".into());
    }

    let mut guard = ENGINE.lock().map_err(|_| "engine lock poisoned")?;
    if let Some(child) = guard.as_mut() {
        if let Ok(None) = child.try_wait() {
            return Ok(()); // already running
        }
    }

    let workdir = path.parent().map(|p| p.to_path_buf());
    let mut cmd = if matches!(ext.as_str(), "bat" | "cmd") {
        let mut c = std::process::Command::new("cmd");
        c.arg("/C").arg(&path);
        c
    } else {
        std::process::Command::new(&path)
    };
    if let Some(dir) = workdir {
        cmd.current_dir(dir);
    }
    let child = cmd.spawn().map_err(|e| format!("Could not start voice engine: {e}"))?;
    *guard = Some(child);
    Ok(())
}

/// Stop the engine if this app launched it.
#[tauri::command]
pub async fn voice_engine_stop() -> Result<(), String> {
    let mut guard = ENGINE.lock().map_err(|_| "engine lock poisoned")?;
    if let Some(mut child) = guard.take() {
        let _ = child.kill();
        let _ = child.wait();
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_local_urls() {
        assert!(is_local("http://127.0.0.1:18888"));
        assert!(is_local("https://localhost:18888"));
        assert!(!is_local("http://example.com"));
    }

    #[test]
    fn default_url() {
        assert_eq!(normalise_url(None), "http://127.0.0.1:18888");
        assert_eq!(normalise_url(Some("http://localhost:18888/".into())), "http://localhost:18888");
    }
}
