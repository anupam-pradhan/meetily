'use client';

/**
 * LiveCopilotPanel
 *
 * Real-time AI suggestions while a call is being recorded.
 * Watches the live transcript and, when new speech arrives, asks the
 * configured LLM (same provider/model as summaries) for:
 *  - what to say next
 *  - a direct answer if a question was just asked
 *  - running key notes / action items
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Copy, Lightbulb, MessageCircleQuestion, NotebookPen, Pause, Play, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useTranscripts } from '@/contexts/TranscriptContext';
import { useRecordingState } from '@/contexts/RecordingStateContext';

interface LiveSuggestions {
  suggestions: string[];
  answer: string;
  notes: string[];
  raw?: string | null;
}

const CONTEXT_KEY = 'copilot.userContext';
const ENABLED_KEY = 'copilot.enabled';
/** Minimum gap between LLM calls (ms) so we don't flood the API. */
const MIN_INTERVAL_MS = 8000;
/** How many recent transcript segments to send. */
const RECENT_SEGMENTS = 40;

function readLocal(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeLocal(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable – ignore */
  }
}

export function LiveCopilotPanel() {
  const { transcripts } = useTranscripts();
  const { isRecording, isPaused } = useRecordingState();

  const [enabled, setEnabled] = useState(true);
  const [userContext, setUserContext] = useState('');
  const [result, setResult] = useState<LiveSuggestions | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lastSentCount = useRef(0);
  const lastCallAt = useRef(0);
  const inFlight = useRef(false);

  useEffect(() => {
    setEnabled(readLocal(ENABLED_KEY, 'true') === 'true');
    setUserContext(readLocal(CONTEXT_KEY, ''));
  }, []);

  // Reset when a new recording starts
  useEffect(() => {
    if (isRecording && transcripts.length === 0) {
      setResult(null);
      setNotes([]);
      lastSentCount.current = 0;
    }
  }, [isRecording, transcripts.length]);

  const fetchSuggestions = useCallback(
    async (force = false) => {
      if (inFlight.current) return;
      const finalSegments = transcripts.filter((t) => !t.is_partial);
      if (finalSegments.length === 0) return;
      if (!force && finalSegments.length === lastSentCount.current) return;
      if (!force && Date.now() - lastCallAt.current < MIN_INTERVAL_MS) return;

      const recent = finalSegments
        .slice(-RECENT_SEGMENTS)
        .map((t) => t.text.trim())
        .filter(Boolean)
        .join('\n');

      inFlight.current = true;
      lastCallAt.current = Date.now();
      lastSentCount.current = finalSegments.length;
      setLoading(true);
      try {
        const res = await invoke<LiveSuggestions>('api_live_suggestions', {
          transcript: recent,
          userContext: userContext || null,
        });
        setResult(res);
        setError(null);
        if (res.notes?.length) {
          setNotes((prev) => {
            const seen = new Set(prev.map((n) => n.toLowerCase()));
            const fresh = res.notes.filter((n) => n && !seen.has(n.toLowerCase()));
            return [...prev, ...fresh];
          });
        }
      } catch (e) {
        setError(typeof e === 'string' ? e : String(e));
      } finally {
        inFlight.current = false;
        setLoading(false);
      }
    },
    [transcripts, userContext]
  );

  // Trigger: new final segment arrives. A question mark triggers immediately;
  // otherwise we wait for the throttle window.
  useEffect(() => {
    if (!enabled || !isRecording || isPaused) return;
    const last = transcripts[transcripts.length - 1];
    const isQuestion = !!last && !last.is_partial && last.text.trim().endsWith('?');
    if (isQuestion && Date.now() - lastCallAt.current > 2000) {
      fetchSuggestions(true);
      return;
    }
    const timer = setTimeout(() => fetchSuggestions(false), 1500);
    return () => clearTimeout(timer);
  }, [transcripts, enabled, isRecording, isPaused, fetchSuggestions]);

  const copy = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => toast.success('Copied'),
      () => toast.error('Could not copy')
    );
  };

  const toggleEnabled = () => {
    const next = !enabled;
    setEnabled(next);
    writeLocal(ENABLED_KEY, String(next));
  };

  return (
    <aside className="w-[340px] shrink-0 border-l border-gray-200 bg-gray-50 flex flex-col overflow-y-auto">
      <div className="sticky top-0 z-10 bg-gray-50 px-4 pt-4 pb-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-amber-500" />
            Live Copilot
          </h2>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fetchSuggestions(true)}
              disabled={loading || transcripts.length === 0}
              title="Refresh suggestions now"
            >
              <RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
            </Button>
            <Button variant="ghost" size="sm" onClick={toggleEnabled} title={enabled ? 'Pause copilot' : 'Resume copilot'}>
              {enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        <Textarea
          className="mt-3 text-xs min-h-[56px] bg-white"
          placeholder="Context for the AI (optional): who you are, goal of the call, product details…"
          value={userContext}
          onChange={(e) => {
            setUserContext(e.target.value);
            writeLocal(CONTEXT_KEY, e.target.value);
          }}
        />
      </div>

      <div className="p-4 space-y-5 text-sm">
        {!isRecording && !result && (
          <p className="text-gray-500 text-xs">
            Start recording a call. Suggestions, answers and key notes will appear here as people talk.
          </p>
        )}

        {error && <p className="text-xs text-red-600 bg-red-50 rounded p-2">{error}</p>}

        {result?.answer && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2 flex items-center gap-1">
              <MessageCircleQuestion className="h-3.5 w-3.5" /> Answer
            </h3>
            <button
              onClick={() => copy(result.answer)}
              className="w-full text-left rounded-lg bg-white border border-blue-200 p-3 hover:border-blue-400"
            >
              {result.answer}
            </button>
          </section>
        )}

        {!!result?.suggestions?.length && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Say next</h3>
            <ul className="space-y-2">
              {result.suggestions.map((s, i) => (
                <li key={i}>
                  <button
                    onClick={() => copy(s)}
                    className="group w-full text-left rounded-lg bg-white border border-gray-200 p-2.5 hover:border-gray-400 flex gap-2"
                  >
                    <span className="flex-1">{s}</span>
                    <Copy className="h-3.5 w-3.5 opacity-0 group-hover:opacity-60 shrink-0 mt-0.5" />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {result?.raw && (
          <section className="rounded-lg bg-white border border-gray-200 p-3 whitespace-pre-wrap">{result.raw}</section>
        )}

        {notes.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 flex items-center gap-1">
                <NotebookPen className="h-3.5 w-3.5" /> Key notes
              </h3>
              <Button variant="ghost" size="sm" onClick={() => copy(notes.map((n) => `• ${n}`).join('\n'))}>
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </div>
            <ul className="space-y-1.5 list-disc pl-4 text-gray-800">
              {notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </aside>
  );
}

export default LiveCopilotPanel;
