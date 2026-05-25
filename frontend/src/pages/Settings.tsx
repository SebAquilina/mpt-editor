import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { Key, ExternalLink, Loader2, CheckCircle2, ArrowLeft } from "lucide-react";

export function Settings() {
  const [params] = useSearchParams();
  const returnTo = params.get("returnTo") || "/";
  const nav = useNavigate();
  const [loading, setLoading] = useState(true);
  const [gem, setGem] = useState("");
  const [pex, setPex] = useState("");
  const [status, setStatus] = useState<{ gemini_configured: boolean; pexels_configured: boolean; gemini_masked: string | null; pexels_masked: string | null } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getKeys().then((s) => { setStatus(s); setLoading(false); }).catch((e) => { setError(String(e)); setLoading(false); });
  }, []);

  const save = async () => {
    setSaving(true); setError(null); setSaved(false);
    try {
      const r = await api.updateKeys(gem || undefined, pex || undefined);
      setStatus({ ...status!, ...r });
      setGem(""); setPex(""); setSaved(true);
      // If both are now configured and we came from elsewhere, return.
      if (r.gemini_configured && r.pexels_configured && returnTo !== "/settings") {
        setTimeout(() => nav(returnTo), 600);
      }
    } catch (e: any) {
      setError(String(e.message || e));
    } finally { setSaving(false); }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading settings…</div>;

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-xl bg-panel border border-border rounded-2xl p-8">
        <button onClick={() => nav(returnTo)} className="text-gray-400 hover:text-white mb-4 inline-flex items-center gap-2 text-sm"><ArrowLeft className="w-4 h-4" /> Back</button>
        <div className="flex items-center gap-3 mb-6">
          <Key className="w-5 h-5 text-accent" />
          <h1 className="text-xl font-semibold">API keys</h1>
        </div>
        <p className="text-sm text-gray-400 mb-6">
          Your keys are stored locally in <code className="bg-bg px-1.5 py-0.5 rounded">.env</code> on the server and never committed to git. Leave a field blank to keep the existing value.
        </p>

        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium mb-1">Gemini API key</label>
            <div className="flex items-center gap-2 mb-2 text-xs">
              <StatusBadge ok={!!status?.gemini_configured} />
              {status?.gemini_masked && <span className="text-gray-500">current: {status.gemini_masked}</span>}
              <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="text-accent inline-flex items-center gap-1 hover:underline">get one <ExternalLink className="w-3 h-3" /></a>
            </div>
            <input type="password" value={gem} onChange={(e) => setGem(e.target.value)} placeholder="AIza…"
                   className="w-full bg-bg border border-border rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-accent" />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Pexels API key</label>
            <div className="flex items-center gap-2 mb-2 text-xs">
              <StatusBadge ok={!!status?.pexels_configured} />
              {status?.pexels_masked && <span className="text-gray-500">current: {status.pexels_masked}</span>}
              <a href="https://www.pexels.com/api/new/" target="_blank" rel="noreferrer" className="text-accent inline-flex items-center gap-1 hover:underline">get one <ExternalLink className="w-3 h-3" /></a>
            </div>
            <input type="password" value={pex} onChange={(e) => setPex(e.target.value)} placeholder="paste Pexels key"
                   className="w-full bg-bg border border-border rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-accent" />
          </div>

          {error && <div className="text-red-400 text-sm">{error}</div>}
          {saved && <div className="text-pex text-sm inline-flex items-center gap-1"><CheckCircle2 className="w-4 h-4" /> Saved.</div>}

          <button onClick={save} disabled={(!gem && !pex) || saving}
                  className="bg-accent text-bg font-semibold px-5 py-2.5 rounded-lg w-full inline-flex items-center justify-center gap-2 disabled:opacity-40">
            {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving…</> : "Save keys"}
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ ok }: { ok: boolean }) {
  return ok
    ? <span className="text-pex text-[10px] uppercase tracking-wider">configured</span>
    : <span className="text-red-400 text-[10px] uppercase tracking-wider">missing</span>;
}
