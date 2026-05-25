import { useEffect, useState } from "react";
import type { Clip } from "../types";
import { api } from "../api/client";
import { X, Loader2, Check } from "lucide-react";

export function AlternatesDrawer({ projectId, clip, onClose, onPicked }: {
  projectId: string; clip: Clip; onClose: () => void; onPicked: (newClip: Clip) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [alts, setAlts] = useState<Clip[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getAlternates(projectId, clip.id)
      .then((r) => { setAlts(r.alternates); setLoading(false); })
      .catch((e) => { setError(String(e.message || e)); setLoading(false); });
  }, [projectId, clip.id]);

  const pick = async (alt: Clip) => {
    try {
      await api.replaceClip(projectId, clip.id, alt.file_path);
      onPicked(alt);
    } catch (e: any) { setError(String(e.message || e)); }
  };

  return (
    <Drawer title={`Choose a replacement for this clip`} subtitle={clip.visual_description || clip.yt_channel || ""} onClose={onClose}>
      {loading ? (
        <div className="text-center text-gray-400 py-10">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-3" />
          Finding 3 alternates via Gemini…
        </div>
      ) : error ? (
        <div className="text-red-400">{error}</div>
      ) : alts.length === 0 ? (
        <div className="text-gray-400">No alternates found. Try the Replace drawer with a specific search query.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {alts.map((a) => (
            <button key={a.id} onClick={() => pick(a)}
                    className="bg-bg border border-border hover:border-accent rounded-lg overflow-hidden text-left transition">
              {a.thumbnail_path && (
                <img src={a.thumbnail_path.startsWith("http") ? a.thumbnail_path : `/api/files/${a.thumbnail_path}`}
                     className="w-full aspect-video object-cover" alt="" />
              )}
              <div className="p-3">
                <div className="text-xs text-accent mb-1 line-clamp-1">{a.yt_channel}</div>
                <div className="text-sm line-clamp-2 mb-1">{a.visual_description}</div>
                <div className="text-xs text-gray-500 flex items-center gap-2">
                  {a.match_quality !== null && <span>{(a.match_quality! * 100).toFixed(0)}% match</span>}
                  <span>· {a.duration_sec.toFixed(1)}s</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </Drawer>
  );
}

export function Drawer({ title, subtitle, onClose, children }: any) {
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end md:items-center justify-center" onClick={onClose}>
      <div className="bg-panel w-full max-w-4xl max-h-[85vh] overflow-y-auto rounded-t-2xl md:rounded-2xl border border-border" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-panel border-b border-border px-6 py-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            {subtitle && <p className="text-sm text-gray-400 mt-0.5">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}
