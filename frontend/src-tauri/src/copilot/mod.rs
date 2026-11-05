//! Live copilot: real-time AI suggestions during a call.
//!
//! Reuses Meetily's existing multi-provider LLM client (`summary::llm_client`)
//! and the provider/model the user already picked in Settings, so no new
//! configuration is needed.

mod prompts;

use crate::database::repositories::setting::SettingsRepository;
use crate::state::AppState;
use crate::summary::llm_client::{generate_summary, LLMProvider};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, Runtime};

/// Keep prompts small and fast: only the tail of the transcript is sent.
const MAX_CONTEXT_CHARS: usize = 6000;
/// Bigger window for on-demand answers and summaries.
const MAX_COPILOT_CHARS: usize = 24000;
/// The copied prompts carry all instructions in the user message.
const COPILOT_SYSTEM: &str = "Follow the instructions in the user message exactly.";

const SYSTEM_PROMPT: &str = "You are a discreet real-time call copilot. \
You read the latest part of a live call transcript and help the user respond well. \
Reply ONLY with compact JSON: \
{\"suggestions\": [\"...\"], \"answer\": \"...\", \"notes\": [\"...\"]}. \
'suggestions' = up to 3 short things the user could say next (max 20 words each). \
'answer' = if the other person just asked a question, a direct 1-2 sentence answer; else an empty string. \
'notes' = up to 3 new key facts, decisions or action items from this part of the call. \
Never invent facts that are not in the transcript or the user's context.";

#[derive(Debug, Serialize, Deserialize, Default)]
pub struct LiveSuggestions {
    #[serde(default)]
    pub suggestions: Vec<String>,
    #[serde(default)]
    pub answer: String,
    #[serde(default)]
    pub notes: Vec<String>,
    /// Raw model text, used as a fallback when the reply was not valid JSON.
    #[serde(default)]
    pub raw: Option<String>,
}

fn tail_chars(text: &str, max: usize) -> &str {
    let count = text.chars().count();
    if count <= max {
        return text;
    }
    let skip = count - max;
    let idx = text.char_indices().nth(skip).map(|(i, _)| i).unwrap_or(0);
    &text[idx..]
}

fn parse_reply(content: &str) -> LiveSuggestions {
    // Models sometimes wrap JSON in ```json fences or add prose around it.
    let start = content.find('{');
    let end = content.rfind('}');
    if let (Some(s), Some(e)) = (start, end) {
        if e > s {
            if let Ok(parsed) = serde_json::from_str::<LiveSuggestions>(&content[s..=e]) {
                return parsed;
            }
        }
    }
    LiveSuggestions {
        raw: Some(content.trim().to_string()),
        ..Default::default()
    }
}

/// Run one prompt through the model the user picked in Settings.
async fn run_llm<R: Runtime>(
    app: &AppHandle<R>,
    state: &tauri::State<'_, AppState>,
    system_prompt: &str,
    user_prompt: &str,
) -> Result<String, String> {
    let pool = state.db_manager.pool();
    let setting = SettingsRepository::get_model_config(pool)
        .await
        .map_err(|e| format!("Could not read model settings: {e}"))?
        .ok_or("No AI model configured. Pick a summary model in Settings first.")?;

    let provider = LLMProvider::from_str(&setting.provider)?;

    let (api_key, custom_endpoint, max_tokens, temperature, top_p) = match provider {
        LLMProvider::Ollama | LLMProvider::BuiltInAI => (String::new(), None, None, None, None),
        LLMProvider::CustomOpenAI => {
            let cfg = SettingsRepository::get_custom_openai_config(pool)
                .await
                .map_err(|e| e.to_string())?
                .ok_or("Custom OpenAI endpoint selected but not configured")?;
            (
                cfg.api_key.unwrap_or_default(),
                Some(cfg.endpoint),
                cfg.max_tokens.map(|t| t as u32),
                cfg.temperature,
                cfg.top_p,
            )
        }
        _ => {
            let key = SettingsRepository::get_api_key(pool, &setting.provider)
                .await
                .map_err(|e| e.to_string())?
                .filter(|k| !k.is_empty())
                .ok_or_else(|| format!("API key not found for {}", setting.provider))?;
            (key, None, None, None, None)
        }
    };

    let client = reqwest::Client::new();
    let app_data_dir = app.path().app_data_dir().ok();

    let completion = generate_summary(
        &client,
        &provider,
        &setting.model,
        &api_key,
        system_prompt,
        user_prompt,
        setting.ollama_endpoint.as_deref(),
        custom_endpoint.as_deref(),
        max_tokens,
        temperature,
        top_p,
        app_data_dir.as_ref(),
        None,
    )
    .await?;
    Ok(completion.content)
}

/// Generate live suggestions from the recent transcript.
///
/// * `transcript` – recent transcript text (the frontend sends the latest lines)
/// * `user_context` – optional notes about the user / goal of the call (e.g. "sales call for product X")
#[tauri::command]
pub async fn api_live_suggestions<R: Runtime>(
    app: AppHandle<R>,
    state: tauri::State<'_, AppState>,
    transcript: String,
    user_context: Option<String>,
) -> Result<LiveSuggestions, String> {
    let transcript = transcript.trim();
    if transcript.is_empty() {
        return Ok(LiveSuggestions::default());
    }

    let mut user_prompt = String::new();
    if let Some(ctx) = user_context.as_deref().map(str::trim).filter(|c| !c.is_empty()) {
        user_prompt.push_str("About me / goal of this call:\n");
        user_prompt.push_str(ctx);
        user_prompt.push_str("\n\n");
    }
    user_prompt.push_str("Latest transcript:\n");
    user_prompt.push_str(tail_chars(transcript, MAX_CONTEXT_CHARS));

    let content = run_llm(&app, &state, SYSTEM_PROMPT, &user_prompt).await?;
    Ok(parse_reply(&content))
}

/// Copilot actions copied from Realtime Interview Copilot (see prompts.rs):
/// * `answer`    – a spoken response to what was just asked
/// * `summary`   – concise summary of the transcript so far
/// * `ask`       – free chat with the AI about the call (`question` required)
#[tauri::command]
pub async fn api_copilot_generate<R: Runtime>(
    app: AppHandle<R>,
    state: tauri::State<'_, AppState>,
    mode: String,
    transcript: String,
    background: Option<String>,
    question: Option<String>,
) -> Result<String, String> {
    let bg = background.as_deref().map(str::trim).filter(|b| !b.is_empty());
    let conversation = tail_chars(transcript.trim(), MAX_COPILOT_CHARS);
    let prompt = match mode.as_str() {
        "answer" => {
            if conversation.is_empty() {
                return Err("Nothing has been said yet.".into());
            }
            prompts::build_prompt(bg, conversation)
        }
        "summary" => {
            if conversation.is_empty() {
                return Err("Nothing has been said yet.".into());
            }
            prompts::build_summarizer_prompt(conversation)
        }
        "ask" => {
            let q = question.as_deref().map(str::trim).filter(|q| !q.is_empty()).ok_or("Type a question first.")?;
            prompts::build_ask_ai_prompt(bg, conversation, q)
        }
        other => return Err(format!("Unknown copilot mode: {other}")),
    };
    // The original app sends the whole prompt as one user message.
    let content = run_llm(&app, &state, COPILOT_SYSTEM, &prompt).await?;
    Ok(content.trim().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_fenced_json() {
        let r = parse_reply("```json\n{\"suggestions\":[\"Ask about budget\"],\"answer\":\"\",\"notes\":[]}\n```");
        assert_eq!(r.suggestions, vec!["Ask about budget"]);
        assert!(r.raw.is_none());
    }

    #[test]
    fn falls_back_to_raw() {
        let r = parse_reply("Say thanks and confirm the date.");
        assert!(r.raw.is_some());
    }

    #[test]
    fn tail_keeps_end() {
        assert_eq!(tail_chars("abcdef", 3), "def");
        assert_eq!(tail_chars("ab", 3), "ab");
    }
}
