import { useEffect, useRef, useState } from "react";
import type { Clip } from "../types";
import { api } from "../api/client";
import { Drawer } from "./AlternatesDrawer";
import { Search, Upload as UploadIcon, Loader2 } from "lucide-react";

type Tab = "leftovers" | "search" | "upload";

export function ReplaceDrawer({ projectId, clip, onClose, onPicked }: {
  projectId: string; clip: Clip; onClose: () => void; onPicked: (newClip: Clip) => void;
}) {
  const [tab, setTab] = useState<Tab>("search");
  return (
    <Drawer title="Replace clip" subtitle={clip.visual_description || ""} onClose={onClose}>
      <div className="flex gap-1 mb-4 bg-bg p-1 rounded-lg w-fit">
        {(["search", "upload"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
                  className={`px-4 py-1.5 text-sm rounded ${tab === t ? "bg-panel text-white" : "text-gray-400"}`}>
            {t === "search" ? "Search" : "Upload"}
          </button>
        ))}
      </div>
      {tab === "search" && <SearchTab projectId={projectId} clip={clip} onPicked={onPicked} />}
      {tab === "upload" && <UploadTab projectId={projectId} clip={clip} onPicked={onPicked} />}
    </Drawer>
  );
}

function SearchTab({ projectId, clip, onPicked }: any) {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Clip[]>([]);
  const search = async () => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const r = await api.searchReplace(projectId, clip.id, q.trim());
      setResults(r.results);
    } finally { setLoading(false); }
  };
  return (
    <div>
      <div className="flex gap-2 mb-4">
        <input value={q} onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && search()}
               placeholder="e.g. wax pouring close-up"
               className="flex-1 bg-bg border border-border rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-accent" />
        <button onClick={search} disabled={loading} className="bg-accent text-bg px-5 rounded-lg font-medium inline-flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />} Search
        </button>
      </div>
      {results.length === 0 && !loading && <p className="text-gray-500 text-sm">Type a query, press Enter. Searches both YouTube and Pexels.</p>}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {results.map((r) => (
          <button key={r.id} onClick={() => onPicked(r)}
                  className="bg-bg border border-border hover:border-accent rounded-lg overflow-hidden text-left transition">
            {r.thumbnail_path && <img src={r.thumbnail_path.startsWith("http") ? r.thumbnail_path : `/api/files/${r.thumbnail_path}`}
                                       className="w-full aspect-video object-cover" alt="" />}
            <div className="p-2 text-xs">
              <div className={r.source === "youtube" ? "text-ytube" : "text-pex"}>{r.source.toUpperCase()}</div>
              <div className="line-clamp-2">{r.yt_video_title || r.pexels_query || ""}</div>
              <div className="text-gray-500">{r.yt_channel || "Pexels"}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function UploadTab({ projectId, clip, onPicked }: any) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const handle = async () => {
    const f = fileRef.current?.files?.[0];
    if (!f) return;
    setUploading(true); setError(null);
    try {
      const r = await api.uploadReplacement(projectId, clip.id, f);
      onPicked({ ...clip, id: r.clip_id, source: "upload", file_path: r.thumbnail_path?.replace("thumbnails", "normalized")?.replace(".jpg", ".mp4") || "", thumbnail_path: r.thumbnail_path });
    } catch (e: any) { setError(String(e.message || e)); }
    finally { setUploading(false); }
  };
  return (
    <div className="text-center py-8">
      <UploadIcon className="w-12 h-12 mx-auto text-gray-500 mb-4" />
      <p className="text-sm text-gray-400 mb-4">Upload an MP4 from your computer. It will be normalized to 1920×1080 and slotted in.</p>
      <input ref={fileRef} type="file" accept="video/mp4" className="text-sm mx-auto" />
      <div className="mt-4">
        <button onClick={handle} disabled={uploading} className="bg-accent text-bg px-5 py-2 rounded font-medium inline-flex items-center gap-2">
          {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadIcon className="w-4 h-4" />}
          {uploading ? "Uploading & normalizing…" : "Upload selected file"}
        </button>
      </div>
      {error && <div className="text-red-400 text-sm mt-3">{error}</div>}
    </div>
  );
}
