import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, subscribeEvents } from "../api/client";
import type { ProjectStatus } from "../types";
import { Loader2 } from "lucide-react";

const STAGE_LABELS: Record<ProjectStatus, string> = {
  queued: "Queued",
  generating_script: "Writing script",
  generating_tts: "Synthesizing narration",
  searching: "Searching YouTube + Pexels",
  matching: "Asking Gemini to match clips to moments",
  downloading: "Downloading clips",
  normalizing: "Normalizing clips",
  ready: "Ready",
  rendering: "Rendering",
  rendered: "Rendered",
  error: "Error",
};
const STAGES: ProjectStatus[] = ["queued","generating_script","generating_tts","searching","matching","downloading","normalizing","ready"];

export function Generating() {
  const { id } = useParams();
  const nav = useNavigate();
  const [status, setStatus] = useState<ProjectStatus>("queued");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getProject(id).then((p) => { setStatus(p.status); setProgress(p.progress); setMessage(p.progress_message); });
    const off = subscribeEvents(id, (ev: any) => {
      if (ev.status) setStatus(ev.status);
      if (typeof ev.progress === "number") setProgress(ev.progress);
      if (ev.message) setMessage(ev.message);
      if (ev.type === "error" || ev.status === "error") setError(ev.message || "Pipeline failed");
      if (ev.type === "done") setTimeout(() => nav(`/projects/${id}/edit`), 600);
    });
    return off;
  }, [id, nav]);

  const stageIdx = STAGES.indexOf(status);

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-xl bg-panel border border-border rounded-2xl p-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="w-5 h-5 text-accent animate-spin" />
          <h1 className="text-xl font-semibold">{STAGE_LABELS[status]}…</h1>
        </div>
        {message && <p className="text-gray-400 text-sm mb-4">{message}</p>}
        <div className="w-full bg-bg rounded-full h-2 mb-6 overflow-hidden">
          <div className="h-full bg-accent transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
        <ol className="space-y-1.5 text-sm">
          {STAGES.filter(s => s !== "queued").map((s, i) => (
            <li key={s} className="flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${i < stageIdx ? "bg-accent" : i === stageIdx ? "bg-accent animate-pulse" : "bg-border"}`}></span>
              <span className={i <= stageIdx ? "text-white" : "text-gray-500"}>{STAGE_LABELS[s]}</span>
            </li>
          ))}
        </ol>
        {error && <div className="mt-6 p-4 bg-red-900/30 border border-red-700/40 text-red-200 text-sm rounded">{error}</div>}
      </div>
    </div>
  );
}
