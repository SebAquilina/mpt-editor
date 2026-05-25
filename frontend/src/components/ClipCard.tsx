import { useState } from "react";
import type { Clip } from "../types";
import { Trash2, RefreshCw, Youtube, Image as ImageIcon, Upload } from "lucide-react";

const SOURCE_COLOR: Record<string, string> = {
  youtube: "border-ytube/60 bg-ytube/10",
  pexels: "border-pex/60 bg-pex/10",
  upload: "border-accent/60 bg-accent/10",
};
const SOURCE_ICON: Record<string, any> = {
  youtube: Youtube, pexels: ImageIcon, upload: Upload,
};

export function ClipCard({ clip, onAction }: { clip: Clip; onAction: (action: "delete" | "replace", clip: Clip) => void; }) {
  const [hover, setHover] = useState(false);
  const Icon = SOURCE_ICON[clip.source];
  const colorClass = SOURCE_COLOR[clip.source];
  const thumbUrl = clip.thumbnail_path
    ? (clip.thumbnail_path.startsWith("http") ? clip.thumbnail_path : `/api/files/${clip.thumbnail_path}`)
    : null;

  return (
    <div
      className={`h-full rounded border-2 ${colorClass} overflow-hidden cursor-grab active:cursor-grabbing relative group`}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      title={clip.visual_description || clip.yt_video_title || clip.source}
    >
      {thumbUrl ? (
        <img src={thumbUrl} alt="" className="w-full h-full object-cover" loading="lazy" />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-gray-500 text-xs">{clip.source}</div>
      )}
      <div className="absolute top-1 left-1 text-[9px] uppercase px-1.5 py-0.5 rounded bg-bg/80 text-gray-200 inline-flex items-center gap-1">
        <Icon className="w-3 h-3" /> {clip.duration_sec.toFixed(1)}s
      </div>
      {clip.match_quality !== null && clip.match_quality !== undefined && (
        <div className="absolute top-1 right-1 text-[9px] px-1 rounded bg-bg/80 text-accent">{(clip.match_quality * 100).toFixed(0)}%</div>
      )}
      {hover && (
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-bg via-bg/80 to-transparent p-1.5 flex items-center justify-center gap-1.5 opacity-0 group-hover:opacity-100 transition">
          <button onClick={(e) => { e.stopPropagation(); onAction("delete", clip); }}
                  className="bg-red-500 hover:bg-red-600 text-white w-7 h-7 rounded inline-flex items-center justify-center" title="Delete (find 3 alternates)">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onAction("replace", clip); }}
                  className="bg-accent hover:bg-accent/90 text-bg w-7 h-7 rounded inline-flex items-center justify-center" title="Replace">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
