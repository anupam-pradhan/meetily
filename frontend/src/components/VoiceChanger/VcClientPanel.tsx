'use client';

/**
 * Advanced: AI voice models via VCClient
 *
 * Optional add-on to the built-in engine. Drives the open-source w-okada VCClient engine (RVC / Beatrice models) for
 * real-time voice conversion, and walks the user through routing the changed
 * voice into any calling app with a virtual microphone (VB-Audio Virtual Cable).
 */

import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { AudioLines, CheckCircle2, CircleAlert, ExternalLink, Play, RefreshCw, Square } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface VcClientStatus {
  reachable: boolean;
  launched_by_app: boolean;
  url: string;
}

const PATH_KEY = 'voiceChanger.enginePath';
const URL_KEY = 'voiceChanger.engineUrl';
const DEFAULT_URL = 'http://127.0.0.1:18888';

function readLocal(key: string, fallback: string) {
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
    /* ignore */
  }
}

const SETUP_STEPS: { title: string; body: string; link?: { label: string; href: string } }[] = [
  {
    title: 'Install the virtual microphone',
    body: 'Install VB-Audio Virtual Cable and restart Windows. It adds “CABLE Input” (a speaker) and “CABLE Output” (a microphone).',
    link: { label: 'vb-audio.com/Cable', href: 'https://vb-audio.com/Cable/' },
  },
  {
    title: 'Install the voice engine',
    body: 'Download VCClient for Windows (ONNX or CUDA build if you have an NVIDIA GPU), unzip it, and paste the path to start_http.bat below.',
    link: { label: 'VCClient downloads (Hugging Face)', href: 'https://huggingface.co/wok000/vcclient000' },
  },
  {
    title: 'Pick devices in the engine',
    body: 'In the engine panel below: input = your real microphone, output = “CABLE Input”. Choose a voice model and press Start.',
  },
  {
    title: 'Use it in your call app',
    body: 'In Zoom, Teams, Meet, WhatsApp or Discord, set the microphone to “CABLE Output”. Everyone on the call now hears the changed voice.',
  },
  {
    title: 'Keep notes working',
    body: 'Meetily still records your real mic and the call audio, so transcription, live suggestions and summaries keep working.',
  },
];

export function VcClientPanel() {
  const [enginePath, setEnginePath] = useState('');
  const [engineUrl, setEngineUrl] = useState(DEFAULT_URL);
  const [status, setStatus] = useState<VcClientStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPanel, setShowPanel] = useState(false);

  useEffect(() => {
    setEnginePath(readLocal(PATH_KEY, ''));
    setEngineUrl(readLocal(URL_KEY, DEFAULT_URL));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const s = await invoke<VcClientStatus>('vcclient_status', { url: engineUrl });
      setStatus(s);
      if (s.reachable) setShowPanel(true);
      return s;
    } catch (e) {
      toast.error(String(e));
      return null;
    }
  }, [engineUrl]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  const start = async () => {
    if (!enginePath.trim()) {
      toast.error('Paste the path to VCClient first (start_http.bat or the .exe).');
      return;
    }
    setBusy(true);
    try {
      await invoke('vcclient_start', { path: enginePath });
      toast.success('Starting voice engine… the first launch can take a minute.');
      // Poll until it answers
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const s = await refresh();
        if (s?.reachable) break;
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    await invoke('vcclient_stop').catch((e) => toast.error(String(e)));
    setShowPanel(false);
    refresh();
  };

  const running = !!status?.reachable;

  return (
    <div>
      <div className="space-y-6">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <AudioLines className="h-4 w-4" /> AI voice models (VCClient)
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              Sound like a different person using RVC voice models. Needs a separate download and works best with an NVIDIA GPU.
              Turn the built-in engine to “Off” while using this, since both write to CABLE Input.
            </p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-medium rounded-full px-3 py-1 ${running ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'
              }`}
          >
            {running ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleAlert className="h-3.5 w-3.5" />}
            {running ? 'Engine running' : 'Engine not running'}
          </span>
        </header>

        <section className="rounded-xl border border-gray-200 p-4 space-y-3">
          <div className="grid gap-3 md:grid-cols-[1fr_220px]">
            <label className="text-xs font-medium text-gray-600 space-y-1">
              <span>VCClient path</span>
              <Input
                placeholder="C:\\vcclient\\start_http.bat"
                value={enginePath}
                onChange={(e) => {
                  setEnginePath(e.target.value);
                  writeLocal(PATH_KEY, e.target.value);
                }}
              />
            </label>
            <label className="text-xs font-medium text-gray-600 space-y-1">
              <span>Engine address</span>
              <Input
                value={engineUrl}
                onChange={(e) => {
                  setEngineUrl(e.target.value);
                  writeLocal(URL_KEY, e.target.value);
                }}
              />
            </label>
          </div>
          <div className="flex gap-2">
            <Button onClick={start} disabled={busy || running}>
              <Play className="h-4 w-4 mr-1" /> {busy ? 'Starting…' : 'Start engine'}
            </Button>
            <Button variant="outline" onClick={stop} disabled={!status?.launched_by_app}>
              <Square className="h-4 w-4 mr-1" /> Stop
            </Button>
            <Button variant="ghost" onClick={refresh}>
              <RefreshCw className="h-4 w-4 mr-1" /> Check
            </Button>
          </div>
          <p className="text-xs text-gray-500">
            Already started VCClient yourself? Just press Check. The engine needs a decent CPU, or an NVIDIA GPU for the lowest delay.
          </p>
        </section>

        {running && showPanel && (
          <section className="rounded-xl border border-gray-200 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-600">
              <span>Engine control panel — choose voice model, input/output devices and pitch</span>
              <a href={status!.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-gray-900">
                Open separately <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <iframe title="Voice engine" src={status!.url} className="w-full h-[640px] bg-white" allow="microphone; autoplay" />
          </section>
        )}

        <section>
          <h4 className="text-xs font-semibold text-gray-700 mb-2">VCClient setup</h4>
          <ol className="grid gap-3 md:grid-cols-2">
            {SETUP_STEPS.map((step, i) => (
              <li key={step.title} className="rounded-lg border border-gray-200 p-3">
                <div className="text-sm font-medium text-gray-900">
                  {i + 1}. {step.title}
                </div>
                <p className="text-xs text-gray-600 mt-1">{step.body}</p>
                {step.link && (
                  <a
                    href={step.link.href}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline inline-flex items-center gap-1 mt-1"
                  >
                    {step.link.label} <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </li>
            ))}
          </ol>
        </section>

      </div>
    </div>
  );
}
