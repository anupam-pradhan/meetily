'use client';

/**
 * Voice & Accent Changer page
 *
 * Controls the built-in voice engine (see frontend/src-tauri/src/voice_engine
 * and voice-engine/ at the repo root):
 *   - Voice effects: 16 presets + pitch, live on your own voice (OpenVoiceChanger)
 *   - Accent: re-speaks what you say in an American or British voice (tok.si)
 * Output goes to the virtual mic "CABLE Output", which the call app uses.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import {
  AudioLines,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Download,
  Globe,
  Loader2,
  Mic,
  MicOff,
  Send,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { VcClientPanel } from '@/components/VoiceChanger/VcClientPanel';

type Mode = 'off' | 'voice' | 'accent';
type AccentWait = 'fast' | 'balanced' | 'smooth';

interface EngineConfig {
  mode: Mode;
  preset: string;
  pitch: number;
  accent_voice: string;
  accent_speed: number;
  accent_wait: AccentWait;
  accent_preset: string;
  mic_device: string | null;
  cable_device: string | null;
}

interface EngineStatus {
  config: EngineConfig;
  stream_live: boolean;
  devices_ok: boolean;
  cable_installed: boolean;
  stream_error: string | null;
  voices_installed: boolean;
  accent_ready: boolean;
  models_error: string | null;
  level_in: number;
  level_out: number;
  last_text: string;
  last_latency_ms: number | null;
  phrases: number;
  setup_task: string | null;
  setup_messages: string[];
  setup_error: string | null;
}

interface Options {
  presets: { id: string; name: string; emoji: string; description: string }[];
  accent_voices: { id: string; label: string }[];
}

interface Devices {
  inputs: { name: string; api: string }[];
  outputs: { name: string; api: string }[];
}

const engine = <T,>(method: 'GET' | 'POST', path: string, body?: unknown) =>
  invoke<T>('voice_engine_request', { method, path, body: body ?? null });

function Meter({ value, label }: { value: number; label: string }) {
  const pct = Math.min(100, Math.round(value * 300));
  return (
    <div className="flex items-center gap-2 text-[11px] text-gray-500">
      <span className="w-10">{label}</span>
      <div className="h-1.5 w-28 rounded-full bg-gray-200 overflow-hidden">
        <div className="h-full bg-green-500 transition-[width] duration-150" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function StatusPill({ ok, okText, badText }: { ok: boolean; okText: string; badText: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium rounded-full px-2.5 py-1 ${ok ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-800'
        }`}
    >
      {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleAlert className="h-3.5 w-3.5" />}
      {ok ? okText : badText}
    </span>
  );
}

export default function VoiceChangerPage() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [devices, setDevices] = useState<Devices | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [starting, setStarting] = useState(true);
  const [sayText, setSayText] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showDevices, setShowDevices] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await engine<EngineStatus>('GET', '/status'));
    } catch (e) {
      setStatus(null);
      setStartError(String(e));
    }
  }, []);

  const startEngine = useCallback(async () => {
    setStarting(true);
    setStartError(null);
    try {
      const s = await invoke<EngineStatus>('voice_engine_ensure');
      setStatus(s);
      const [opts, devs] = await Promise.all([engine<Options>('GET', '/options'), engine<Devices>('GET', '/devices')]);
      setOptions(opts);
      setDevices(devs);
    } catch (e) {
      setStartError(String(e));
    } finally {
      setStarting(false);
    }
  }, []);

  useEffect(() => {
    startEngine();
  }, [startEngine]);

  // Fast polling for meters while the page is open
  useEffect(() => {
    if (!status) return;
    pollRef.current = setInterval(refresh, 700);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [status !== null, refresh]); // eslint-disable-line react-hooks/exhaustive-deps

  const setConfig = async (changes: Partial<EngineConfig>) => {
    try {
      await engine('POST', '/config', changes);
      await refresh();
    } catch (e) {
      toast.error(String(e));
    }
  };

  const runSetup = async (what: 'voices' | 'cable') => {
    try {
      await engine('POST', '/setup', { what });
      toast.message(what === 'voices' ? 'Downloading accent voices…' : 'Starting the virtual mic installer…');
      await refresh();
    } catch (e) {
      toast.error(String(e));
    }
  };

  const say = async () => {
    const text = sayText.trim();
    if (!text) return;
    try {
      await engine('POST', '/say', { text });
      setSayText('');
    } catch (e) {
      toast.error(String(e));
    }
  };

  const cfg = status?.config;
  const busy = !!status?.setup_task;

  return (
    <div className="flex flex-col h-screen overflow-y-auto bg-white">
      <div className="max-w-5xl w-full mx-auto px-6 py-6 space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <AudioLines className="h-5 w-5" /> Voice &amp; Accent Changer
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Change how you sound on any call: Zoom, Teams, Meet, WhatsApp, Discord, Slack.
            </p>
          </div>
          {status && (
            <div className="flex flex-wrap gap-2">
              <StatusPill ok={status.cable_installed} okText="Virtual mic ready" badText="Virtual mic missing" />
              <StatusPill ok={status.stream_live} okText="Mic live" badText="Mic not connected" />
            </div>
          )}
        </header>

        {starting && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Loader2 className="h-4 w-4 animate-spin" /> Starting the voice engine…
          </div>
        )}
        {startError && !status && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 space-y-2">
            <p>{startError}</p>
            <Button size="sm" variant="outline" onClick={startEngine}>
              Try again
            </Button>
          </div>
        )}

        {status && cfg && (
          <>
            {/* One-time setup */}
            {(!status.cable_installed || !status.voices_installed || busy || status.setup_error) && (
              <section className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 space-y-3">
                <h2 className="text-sm font-semibold text-gray-900">One-time setup</h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-lg bg-white border border-gray-200 p-3">
                    <div className="text-sm font-medium">1. Virtual microphone</div>
                    <p className="text-xs text-gray-600 mt-1">
                      Installs VB-Audio Virtual Cable. Windows will ask for permission. Click “Install Driver”, then restart
                      if asked.
                    </p>
                    <Button
                      size="sm"
                      className="mt-2"
                      disabled={status.cable_installed || busy}
                      onClick={() => runSetup('cable')}
                    >
                      {status.cable_installed ? 'Installed' : 'Install virtual mic'}
                    </Button>
                  </div>
                  <div className="rounded-lg bg-white border border-gray-200 p-3">
                    <div className="text-sm font-medium">2. Accent voices</div>
                    <p className="text-xs text-gray-600 mt-1">
                      Downloads the speech model and 8 English voices (about 440 MB, once). Not needed for voice effects.
                    </p>
                    <Button
                      size="sm"
                      className="mt-2"
                      disabled={status.voices_installed || busy}
                      onClick={() => runSetup('voices')}
                    >
                      <Download className="h-4 w-4 mr-1" />
                      {status.voices_installed ? 'Installed' : 'Download voices'}
                    </Button>
                  </div>
                </div>
                {(busy || status.setup_messages.length > 0) && (
                  <div className="text-xs text-gray-700 bg-white rounded border border-gray-200 p-2 space-y-0.5">
                    {busy && (
                      <div className="flex items-center gap-1.5 font-medium">
                        <Loader2 className="h-3 w-3 animate-spin" /> Working…
                      </div>
                    )}
                    {status.setup_messages.map((m, i) => (
                      <div key={i}>{m}</div>
                    ))}
                  </div>
                )}
                <p className="text-xs text-gray-600">
                  Then in your call app, set <b>Microphone</b> to <b>CABLE Output (VB-Audio Virtual Cable)</b> and keep the
                  speaker on your headset.
                </p>
              </section>
            )}

            {/* Mode */}
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-gray-900">What the other person hears</h2>
              <div className="grid gap-3 md:grid-cols-3">
                {(
                  [
                    { id: 'off', icon: Mic, title: 'My real voice', body: 'Your microphone, unchanged. No delay.' },
                    { id: 'voice', icon: Sparkles, title: 'Voice effects', body: 'Deeper, higher, robot and more. No delay.' },
                    {
                      id: 'accent',
                      icon: Globe,
                      title: 'Accent changer',
                      body: 'You speak; they hear an American or British voice. About 1 second delay.',
                    },
                  ] as const
                ).map(({ id, icon: Icon, title, body }) => {
                  const active = cfg.mode === id;
                  const disabled = id === 'accent' && !status.voices_installed;
                  return (
                    <button
                      key={id}
                      disabled={disabled}
                      onClick={() => setConfig({ mode: id })}
                      className={`text-left rounded-xl border p-4 transition-colors ${active ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-gray-200 hover:border-gray-400'
                        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      <div className="flex items-center gap-2 font-medium text-gray-900">
                        <Icon className="h-4 w-4" /> {title}
                      </div>
                      <p className="text-xs text-gray-600 mt-1">{disabled ? 'Download the accent voices first.' : body}</p>
                    </button>
                  );
                })}
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <Meter label="Mic" value={status.level_in} />
                <Meter label="Call" value={status.level_out} />
                {status.stream_error && <span className="text-xs text-red-600">{status.stream_error}</span>}
              </div>
            </section>

            {/* Voice effects */}
            {cfg.mode === 'voice' && options && (
              <section className="rounded-xl border border-gray-200 p-4 space-y-4">
                <div className="grid gap-2 grid-cols-2 sm:grid-cols-4">
                  {options.presets.map((p) => (
                    <button
                      key={p.id}
                      title={p.description}
                      onClick={() => setConfig({ preset: p.id })}
                      className={`rounded-lg border px-3 py-2 text-left text-sm ${cfg.preset === p.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-400'
                        }`}
                    >
                      <span className="mr-1.5">{p.emoji}</span>
                      {p.name}
                    </button>
                  ))}
                </div>
                <label className="block text-xs text-gray-600">
                  Extra pitch: {cfg.pitch > 0 ? '+' : ''}
                  {cfg.pitch} semitones
                  <input
                    type="range"
                    min={-12}
                    max={12}
                    step={1}
                    value={cfg.pitch}
                    onChange={(e) => setConfig({ pitch: Number(e.target.value) })}
                    className="w-full mt-1"
                  />
                </label>
              </section>
            )}

            {/* Accent */}
            {cfg.mode === 'accent' && options && (
              <section className="rounded-xl border border-gray-200 p-4 space-y-4">
                {!status.accent_ready && !status.models_error && (
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading accent voices…
                  </div>
                )}
                {status.models_error && <p className="text-sm text-red-600">{status.models_error}</p>}
                <div className="grid gap-4 md:grid-cols-3">
                  <label className="text-xs text-gray-600 space-y-1">
                    <span>Accent and voice</span>
                    <select
                      className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                      value={cfg.accent_voice}
                      onChange={(e) => setConfig({ accent_voice: e.target.value })}
                    >
                      {options.accent_voices.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs text-gray-600 space-y-1">
                    <span>Speed vs. smoothness</span>
                    <select
                      className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                      value={cfg.accent_wait}
                      onChange={(e) => setConfig({ accent_wait: e.target.value as AccentWait })}
                    >
                      <option value="fast">Fastest: may split long sentences</option>
                      <option value="balanced">Balanced (recommended)</option>
                      <option value="smooth">Smoothest: waits for longer phrases</option>
                    </select>
                  </label>
                  <label className="text-xs text-gray-600 space-y-1">
                    <span>Talking speed: {cfg.accent_speed.toFixed(1)}×</span>
                    <input
                      type="range"
                      min={0.7}
                      max={1.4}
                      step={0.1}
                      value={cfg.accent_speed}
                      onChange={(e) => setConfig({ accent_speed: Number(e.target.value) })}
                      className="w-full"
                    />
                  </label>
                </div>

                <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-sm">
                  <div className="text-xs text-gray-500 mb-1">
                    Last line spoken{status.last_latency_ms != null ? ` · ${status.last_latency_ms} ms` : ''}
                  </div>
                  <div className="text-gray-900 min-h-[1.25rem]">{status.last_text || 'Start talking…'}</div>
                </div>

                <div>
                  <div className="text-xs text-gray-600 mb-1">Type to speak: say it in the accent voice without talking</div>
                  <div className="flex gap-2">
                    <Textarea
                      className="min-h-[40px] text-sm"
                      value={sayText}
                      placeholder="Type a sentence and press Send (Ctrl+Enter)"
                      onChange={(e) => setSayText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) say();
                      }}
                    />
                    <Button onClick={say} disabled={!sayText.trim() || !status.accent_ready}>
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                <p className="text-xs text-gray-500">
                  The other person hears a different, natural English voice saying your words. Your own voice isn’t sent.
                  It can mishear a word. Keep calls where every word matters on your real voice until you’ve tested it.
                </p>
              </section>
            )}

            {/* Devices */}
            <section className="rounded-xl border border-gray-200">
              <button
                className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-900"
                onClick={async () => {
                  setShowDevices((v) => !v);
                  if (!devices) setDevices(await engine<Devices>('GET', '/devices').catch(() => null));
                }}
              >
                <span className="flex items-center gap-2">
                  {status.stream_live ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />} Microphone and
                  output
                </span>
                {showDevices ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              {showDevices && (
                <div className="px-4 pb-4 grid gap-3 md:grid-cols-2">
                  <label className="text-xs text-gray-600 space-y-1">
                    <span>Your microphone</span>
                    <select
                      className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                      value={cfg.mic_device ?? ''}
                      onChange={(e) => setConfig({ mic_device: e.target.value || null })}
                    >
                      <option value="">Automatic (headset first)</option>
                      {[...new Set((devices?.inputs ?? []).filter((d) => !/cable/i.test(d.name)).map((d) => d.name))].map(
                        (n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        )
                      )}
                    </select>
                  </label>
                  <label className="text-xs text-gray-600 space-y-1">
                    <span>Send to (virtual mic)</span>
                    <select
                      className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                      value={cfg.cable_device ?? ''}
                      onChange={(e) => setConfig({ cable_device: e.target.value || null })}
                    >
                      <option value="">CABLE Input (VB-Audio Virtual Cable)</option>
                      {[...new Set((devices?.outputs ?? []).map((d) => d.name))].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="text-xs text-gray-500 md:col-span-2">
                    Use a headset. With laptop speakers, the other person’s voice can leak into your mic and get repeated.
                  </p>
                </div>
              )}
            </section>
          </>
        )}

        {/* Advanced: AI voice models */}
        <section className="rounded-xl border border-gray-200">
          <button
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-900"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            <span>Advanced: AI voice models (sound like another person)</span>
            {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
          {showAdvanced && (
            <div className="px-4 pb-4">
              <VcClientPanel />
            </div>
          )}
        </section>

        <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900 space-y-1">
          <p className="font-medium">Use responsibly</p>
          <p>
            Don’t use voice or accent changing to pretend to be someone else, to deceive people, or where the law or the
            other side requires your real voice. Tell people on the call when you are recording.
          </p>
        </section>
      </div>
    </div>
  );
}
