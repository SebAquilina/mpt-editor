import { useEffect, useRef, useState } from "react";
import type { Project, Clip } from "../types";
import { ScriptTrack } from "./ScriptTrack";
import { ClipTrack } from "./ClipTrack";

interface Props {
  project: Project;
  pxPerSec: number;
  onClipAction: (action: "delete" | "replace", clip: Clip) => void;
  onClipReorder: (paragraphId: number, ordered: string[]) => void;
  playhead: number;
  onSeek: (t: number) => void;
}

export function Timeline({ project, pxPerSec, onClipAction, onClipReorder, playhead, onSeek }: Props) {
  const totalDur = project.paragraphs.reduce((s, p) => s + p.audio_duration_sec, 0);
  const totalPx = totalDur * pxPerSec;
  const wrapRef = useRef<HTMLDivElement>(null);

  return (
    <div className="bg-panel border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-border flex items-center justify-between text-xs text-gray-400">
        <div>{project.paragraphs.length} paragraphs · {totalDur.toFixed(1)}s</div>
        <div>Click a clip to edit it</div>
      </div>
      <div className="overflow-x-auto" ref={wrapRef}>
        <div style={{ width: Math.max(totalPx, 800), minWidth: "100%" }} className="relative">
          <TimeRuler totalDur={totalDur} pxPerSec={pxPerSec} onSeek={onSeek} />
          <ScriptTrack project={project} pxPerSec={pxPerSec} />
          <ClipTrack project={project} pxPerSec={pxPerSec}
                     onClipAction={onClipAction} onClipReorder={onClipReorder} />
          <Playhead pos={playhead * pxPerSec} totalDur={totalDur} pxPerSec={pxPerSec} />
        </div>
      </div>
    </div>
  );
}

function TimeRuler({ totalDur, pxPerSec, onSeek }: { totalDur: number; pxPerSec: number; onSeek: (t: number) => void; }) {
  const ticks: number[] = [];
  const step = pxPerSec < 30 ? 30 : pxPerSec < 60 ? 10 : 5;
  for (let t = 0; t <= totalDur; t += step) ticks.push(t);
  const handleClick = (e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    onSeek((e.clientX - rect.left) / pxPerSec);
  };
  return (
    <div onClick={handleClick} className="relative h-6 bg-bg/50 border-b border-border cursor-pointer select-none">
      {ticks.map((t) => (
        <div key={t} style={{ left: t * pxPerSec }} className="absolute top-0 h-full border-l border-border/60 text-[10px] text-gray-500 pl-1">
          {fmt(t)}
        </div>
      ))}
    </div>
  );
}
function fmt(s: number) {
  const m = Math.floor(s / 60); const r = Math.floor(s % 60);
  return `${m}:${r.toString().padStart(2, "0")}`;
}
function Playhead({ pos }: { pos: number; totalDur: number; pxPerSec: number; }) {
  return <div style={{ left: pos }} className="absolute top-0 bottom-0 w-px bg-red-500 pointer-events-none z-30">
    <div className="absolute -top-1 -left-1.5 w-3 h-3 bg-red-500 rounded-full"></div>
  </div>;
}
