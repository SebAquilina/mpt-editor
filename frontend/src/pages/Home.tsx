import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Sparkles, ArrowRight, Settings as SettingsIcon } from "lucide-react";

const EXAMPLES = [
  "How to make DIY soy candles at home — beginner's complete guide",
  "How to brew the perfect espresso at home",
  "Beginner's guide to sourdough bread",
  "How to set up a productive home office",
];

export function Home() {
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nav = useNavigate();
  const [keysOk, setKeysOk] = useState<boolean | null>(null);

  useEffect(() => {
    api.getKeys().then(k => setKeysOk(k.gemini_configured && k.pexels_configured));
  }, []);

  const submit = async () => {
    if (!prompt.trim()) return;
    setSubmitting(true); setError(null);
    try {
      const r = await api.createProject(prompt.trim());
      nav(`/projects/${r.project_id}/generating`);
    } catch (e: any) {
      setError(String(e.message || e));
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 text-accent text-sm mb-3">
            <Sparkles className="w-4 h-4" /> mpt-editor
          </div>
          <h1 className="text-4xl font-bold mb-3">What should we make a video about?</h1>
          <p className="text-gray-400">
            One prompt → Gemini writes a script, finds matching YouTube clips, fills the rest with Pexels, and drops you into an editor.
          </p>
        </div>
        {keysOk === false && (
          <div className="bg-red-900/30 border border-red-700/40 rounded-xl px-4 py-3 mb-4 text-sm flex items-center justify-between">
            <div><strong>API keys missing.</strong> Set them once before generating videos.</div>
            <button onClick={() => nav("/settings?returnTo=/")} className="bg-accent text-bg px-3 py-1.5 rounded font-medium inline-flex items-center gap-1.5 text-xs"><SettingsIcon className="w-3.5 h-3.5" /> Configure</button>
          </div>
        )}
        <div className="bg-panel border border-border rounded-2xl p-6">
          <textarea
            className="w-full bg-bg border border-border rounded-lg p-4 text-white placeholder-gray-500 focus:outline-none focus:border-accent resize-none min-h-[100px]"
            placeholder="e.g. How to make DIY soy candles at home — beginner's complete guide"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit(); }}
          />
          <div className="flex items-center justify-between mt-4">
            <span className="text-xs text-gray-500">⌘+Enter to submit</span>
            <button
              onClick={submit}
              disabled={!prompt.trim() || submitting || keysOk === false}
              className="bg-accent text-bg font-semibold px-5 py-2 rounded-lg inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-accent/90 transition"
            >
              {submitting ? "Starting…" : <>Generate <ArrowRight className="w-4 h-4" /></>}
            </button>
          </div>
          {error && <div className="text-red-400 text-sm mt-3">{error}</div>}
        </div>
        <div className="mt-8">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">Try one of these</div>
          <div className="space-y-2">
            {EXAMPLES.map((ex) => (
              <button key={ex} onClick={() => setPrompt(ex)}
                className="block w-full text-left bg-panel/50 border border-border rounded-lg px-4 py-3 text-sm hover:bg-panel hover:border-accent/40 transition">
                {ex}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
