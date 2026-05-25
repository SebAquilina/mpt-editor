import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { Key, ExternalLink, Loader2, CheckCircle2, ArrowLeft, Cookie, Upload, Trash2 } from "lucide-react";

export function Settings() {
  const [params] = useSearchParams();
  const returnTo = params.get("returnTo") || "/";
  const nav = useNavigate();
  const [loading, setLoading] = useState(true);
  const [gem, setGem] = useState("");
  const [pex, setPex] = useState("");
  const [status, setStatus] = useState<{ gemini_configured: boolean; pexels_configured: boolean; gemini_masked: string | null; pexels_masked: string | null } | null>(null);
  const [cookies, setCookies] = useState<{ uploaded: boolean; size_bytes: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const cookieFileRef = useRef<HTMLInputElement>(null);
  const [cookieUploading, setCookieUploading] = useState(false);
  const [cookieMsg, setCookieMsg] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getKeys(), api.getCookiesStatus()]).then(([s, c]) => { setStatus(s); setCookies(c); setLoading(false); }).catch((e) => { setError(String(e)); setLoading(false); });
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

          <div className="border-t border-border pt-5">
            <div className="flex items-center gap-2 mb-2">
              <Cookie className="w-4 h-4 text-accent" />
              <h2 className="text-sm font-semibold">YouTube cookies (optional)</h2>
            </div>
            <p className="text-xs text-gray-400 mb-3 leading-relaxed">
              YouTube blocks anonymous downloads from cloud-provider IPs (Codespaces, AWS, GCP). To get the 80-90% YouTube clip mix, export your YouTube cookies as a Netscape <code>cookies.txt</code> using a browser extension like "Get cookies.txt LOCALLY", then upload it here. Stored at <code>data/youtube_cookies.txt</code>, gitignored, never committed.
            </p>
            <div className="flex items-center gap-2 mb-2 text-xs">
              {cookies?.uploaded
                ? <span className="text-pex">UPLOADED ({(cookies.size_bytes / 1024).toFixed(1)} KB)</span>
                : <span className="text-yellow-400">NOT UPLOADED (pipeline will fall back to Pexels for YouTube downloads)</span>}
            </div>
            <div className="flex items-center gap-2">
              <input ref={cookieFileRef} type="file" accept=".txt" className="text-xs flex-1" />
              <button
                onClick={async () => {
                  const f = cookieFileRef.current?.files?.[0];
                  if (!f) { setCookieMsg("pick a file first"); return; }
                  setCookieUploading(true); setCookieMsg(null);
                  try {
                    const r = await api.uploadCookies(f);
                    setCookies(r); setCookieMsg("uploaded successfully");
                  } catch (e: any) { setCookieMsg(String(e.message || e)); }
                  finally { setCookieUploading(false); }
                }}
                disabled={cookieUploading}
                className="bg-bg border border-border hover:border-accent px-3 py-1.5 rounded text-xs inline-flex items-center gap-1.5">
                {cookieUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                Upload
              </button>
              {cookies?.uploaded && (
                <button
                  onClick={async () => { await api.deleteCookies(); setCookies({ uploaded: false, size_bytes: 0 }); setCookieMsg("removed"); }}
                  className="text-red-400 hover:text-red-300 px-2 py-1.5 rounded text-xs inline-flex items-center gap-1">
                  <Trash2 className="w-3.5 h-3.5" /> Remove
                </button>
              )}
            </div>
            {cookieMsg && <div className="text-xs text-gray-400 mt-2">{cookieMsg}</div>}
          </div>
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
