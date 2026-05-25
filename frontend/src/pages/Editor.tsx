import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api, subscribeEvents } from "../api/client";
import type { Project, Clip } from "../types";
import { Timeline } from "../components/Timeline";
import { PreviewPlayer } from "../components/PreviewPlayer";
import { AlternatesDrawer } from "../components/AlternatesDrawer";
import { ReplaceDrawer } from "../components/ReplaceDrawer";
import { Play, Pause, Download, RefreshCw, ArrowLeft, Loader2 } from "lucide-react";

export function Editor() {
  const { id } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [playhead, setPlayhead] = useState(0);
  const [pxPerSec, setPxPerSec] = useState(28);
  const [drawer, setDrawer] = useState<{ kind: "alternates" | "replace"; clip: Clip } | null>(null);
  const [rendering, setRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState<number>(0);
  const [renderMsg, setRenderMsg] = useState<string>("");
  const [finalVideoUrl, setFinalVideoUrl] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!id) return;
    try { const p = await api.getProject(id); setProject(p); }
    catch (e: any) { setError(String(e.message || e)); }
  }, [id]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (!id) return;
    const off = subscribeEvents(id, (ev: any) => {
      if (ev.type === "render_progress") { setRenderProgress(ev.progress); setRenderMsg(ev.message); }
      if (ev.type === "render_done") {
        setFinalVideoUrl(`/api/files/${ev.video_path}`);
        setRendering(false);
        refresh();
      }
      if (ev.type === "render_error") { setError(`Render failed: ${ev.message}`); setRendering(false); }
    });
    return off;
  }, [id, refresh]);

  if (error) return <div className="p-10 text-red-400">{error}</div>;
  if (!project) return <div className="p-10 text-gray-400 inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>;

  const totalDur = project.paragraphs.reduce((s, p) => s + p.audio_duration_sec, 0);
  const audioUrl = project.full_audio_path ? `/api/files/${project.full_audio_path}` : null;

  const handleClipAction = (action: "delete" | "replace", clip: Clip) =>
    setDrawer({ kind: action === "delete" ? "alternates" : "replace", clip });
  const handlePicked = async () => { setDrawer(null); await refresh(); };

  const onReorder = async (paraId: number, ordered: string[]) => {
    try { await api.reorderClips(project.id, paraId, ordered); refresh(); }
    catch (e: any) { setError(String(e.message || e)); }
  };

  const startRender = async () => {
    setRendering(true); setRenderProgress(0); setFinalVideoUrl(null);
    try { await api.render(project.id); }
    catch (e: any) { setError(String(e.message || e)); setRendering(false); }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-panel border-b border-border px-6 py-3 flex items-center gap-4">
        <Link to="/" className="text-gray-400 hover:text-white"><ArrowLeft className="w-4 h-4" /></Link>
        <div className="flex-1">
          <h1 className="font-semibold leading-tight">{project.title}</h1>
          <p className="text-xs text-gray-400 line-clamp-1">{project.prompt}</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <label className="text-gray-400">zoom</label>
          <input type="range" min={10} max={60} value={pxPerSec} onChange={(e) => setPxPerSec(Number(e.target.value))} className="w-32" />
        </div>
        <button onClick={() => setPlaying(!playing)} className="bg-panel border border-border w-9 h-9 rounded inline-flex items-center justify-center">
          {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>
        <button onClick={startRender} disabled={rendering}
                className="bg-accent text-bg font-semibold px-4 py-2 rounded inline-flex items-center gap-2 disabled:opacity-50">
          {rendering ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {rendering ? `Rendering ${renderProgress}%` : "Render"}
        </button>
        {finalVideoUrl && (
          <a href={finalVideoUrl} download className="bg-pex text-white font-semibold px-4 py-2 rounded inline-flex items-center gap-2">
            <Download className="w-4 h-4" /> MP4
          </a>
        )}
      </header>
      <main className="flex-1 flex flex-col p-6 gap-4 overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <PreviewPlayer audioUrl={audioUrl} videoUrl={finalVideoUrl} playing={playing}
                         playhead={playhead}
                         onTimeUpdate={setPlayhead}
                         onEnded={() => setPlaying(false)} />
          <div className="bg-panel border border-border rounded-xl p-4 text-sm">
            <div className="font-medium mb-2">Project</div>
            <dl className="grid grid-cols-3 gap-2 text-xs">
              <dt className="text-gray-400">Duration</dt><dd className="col-span-2">{totalDur.toFixed(1)}s ({(totalDur/60).toFixed(1)} min)</dd>
              <dt className="text-gray-400">Paragraphs</dt><dd className="col-span-2">{project.paragraphs.length}</dd>
              <dt className="text-gray-400">Clips total</dt><dd className="col-span-2">{project.paragraphs.reduce((s,p) => s + p.clips.length, 0)}</dd>
              <dt className="text-gray-400">YouTube</dt><dd className="col-span-2">{project.paragraphs.reduce((s,p) => s + p.clips.filter(c => c.source==="youtube").length, 0)}</dd>
              <dt className="text-gray-400">Pexels</dt><dd className="col-span-2">{project.paragraphs.reduce((s,p) => s + p.clips.filter(c => c.source==="pexels").length, 0)}</dd>
              <dt className="text-gray-400">Status</dt><dd className="col-span-2">{project.status}</dd>
            </dl>
            {rendering && (
              <div className="mt-4">
                <div className="text-xs text-gray-400 mb-1">{renderMsg}</div>
                <div className="w-full bg-bg rounded-full h-1.5"><div className="h-full bg-accent" style={{width:`${renderProgress}%`}}/></div>
              </div>
            )}
          </div>
        </div>
        <Timeline project={project} pxPerSec={pxPerSec}
                  onClipAction={handleClipAction}
                  onClipReorder={onReorder}
                  playhead={playhead} onSeek={setPlayhead} />
      </main>
      {drawer?.kind === "alternates" && <AlternatesDrawer projectId={project.id} clip={drawer.clip} onClose={() => setDrawer(null)} onPicked={handlePicked} />}
      {drawer?.kind === "replace" && <ReplaceDrawer projectId={project.id} clip={drawer.clip} onClose={() => setDrawer(null)} onPicked={handlePicked} />}
    </div>
  );
}
