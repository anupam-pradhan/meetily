//! Copilot prompts.
//!
//! Ported from Realtime Interview Copilot by Ved Prakash Gupta
//! https://github.com/innovatorved/realtime-interview-copilot
//! file realtime-worker-api/src/lib/prompt.ts (commit c974067)
//! Licensed under the Apache License, Version 2.0 (see THIRD_PARTY_NOTICES.md).
//!
//! Changes made (Apache-2.0 §4(b)):
//! - translated from TypeScript to Rust
//! - "interview coach"/"candidate"/"interview" wording generalised to any call
//!   (sales, support, meetings, interviews)
//! - `build_ask_ai_prompt` also receives the call transcript so far
//! - `build_summarizer_prompt` asks for key points and action items

pub fn build_prompt(bg: Option<&str>, conversation: &str) -> String {
    format!(
        "You are a live call coach. Given the background and conversation below, craft a spoken response the user can deliver confidently.

Rules:
- Open with a direct answer, then support it with 3–5 concise points
- Use field-appropriate terminology; write how people speak, not how they type
- Close with a brief real-world example or hands-on tie-in when relevant
- No meta-text (\"Here's a response…\") — just the answer itself
- Aim for ~1–2 minutes of speaking material

BACKGROUND: {}

CONVERSATION:
{}

RESPONSE:",
        bg.unwrap_or("None provided"),
        conversation
    )
}

pub fn build_summarizer_prompt(text: &str) -> String {
    format!(
        "Summarize concisely. Then list key decisions and action items (with owners if mentioned). Output only the summary.

{}",
        text
    )
}

pub fn build_ask_ai_prompt(bg: Option<&str>, conversation: &str, user_question: &str) -> String {
    format!(
        "You are a helpful assistant in the \"Ask AI\" chat during a live call. The human user is speaking directly TO YOU — they are NOT the other person on the call, and their messages are NOT a transcript unless they explicitly say so.

Your job: answer the user's question clearly and directly. Help them during the call (explain concepts, draft answers, check facts from the conversation, review their approach, etc.).

Rules:
- Treat every user message as a question or request directed at you
- Do NOT role-play as if the user quoted the other person unless they explicitly paste a line and ask you to help answer it
- Do NOT write a \"spoken script to read aloud\" unless the user explicitly asks for that
- Use the BACKGROUND and the CONVERSATION SO FAR when relevant
- Be concise but thorough; use markdown lists or code blocks when helpful
- Start with the answer itself — no preamble, no filler, no acknowledging their topic first
- NEVER open with phrases like \"It looks like…\", \"Great question!\", \"Sure!\", \"I'd be happy to…\", or \"You're interested in…\" — go straight to substance
- No meta-commentary (\"Here's what you need to know\", \"Let me explain\") — just explain

BACKGROUND:
{}

CONVERSATION SO FAR:
{}

USER:
{}

ASSISTANT:",
        bg.unwrap_or("None provided"),
        if conversation.is_empty() { "(nothing said yet)" } else { conversation },
        user_question
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prompts_include_inputs() {
        let p = build_prompt(Some("I sell CRM software"), "Them: what does it cost?");
        assert!(p.contains("I sell CRM software") && p.contains("what does it cost?") && p.ends_with("RESPONSE:"));
        assert!(build_prompt(None, "x").contains("BACKGROUND: None provided"));
        let a = build_ask_ai_prompt(None, "", "What did they say about pricing?");
        assert!(a.contains("(nothing said yet)") && a.contains("pricing"));
        assert!(build_summarizer_prompt("hello").ends_with("hello"));
    }
}
