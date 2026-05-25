import type { Project } from "../types";

export function ScriptTrack({ project, pxPerSec }: { project: Project; pxPerSec: number; }) {
  return (
    <div className="relative h-20 bg-bg/30 border-b border-border">
      <div className="absolute left-2 top-1 text-[10px] text-gray-500 uppercase tracking-wider pointer-events-none z-10">Script · TTS</div>
      {project.paragraphs.flatMap((p) =>
        p.sentences.map((s) => {
          const left = s.start_sec * pxPerSec;
          const width = (s.end_sec - s.start_sec) * pxPerSec;
          return (
            <div key={s.id} title={s.text}
                 style={{ left, width }}
                 className="absolute top-5 bottom-1 bg-accent/15 hover:bg-accent/30 border-l border-accent/40 px-1.5 py-1 overflow-hidden text-[11px] leading-tight text-gray-200 transition">
              {s.text}
            </div>
          );
        })
      )}
      {project.paragraphs.map((p, i) => i === 0 ? null : (
        <div key={`pb-${p.id}`} style={{ left: p.timeline_start_sec * pxPerSec }}
             className="absolute top-0 bottom-0 border-l-2 border-accent/60 z-20"
             title={`Paragraph ${p.id}`} />
      ))}
    </div>
  );
}
