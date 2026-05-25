import { useState } from "react";
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, useSortable, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Project, Clip } from "../types";
import { ClipCard } from "./ClipCard";

interface Props {
  project: Project;
  pxPerSec: number;
  onClipAction: (action: "delete" | "replace", clip: Clip) => void;
  onClipReorder: (paragraphId: number, ordered: string[]) => void;
}

export function ClipTrack({ project, pxPerSec, onClipAction, onClipReorder }: Props) {
  return (
    <div className="relative bg-bg/30">
      <div className="absolute left-2 top-1 text-[10px] text-gray-500 uppercase tracking-wider pointer-events-none z-10">Clips</div>
      <div className="relative h-32 pt-5">
        {project.paragraphs.map((p) => (
          <ParagraphClips key={p.id} paragraph={p} pxPerSec={pxPerSec}
                          onClipAction={onClipAction} onReorder={(ids) => onClipReorder(p.id, ids)} />
        ))}
      </div>
    </div>
  );
}

function ParagraphClips({ paragraph, pxPerSec, onClipAction, onReorder }: any) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const ids = paragraph.clips.map((c: Clip) => c.id);
  const onDragEnd = (e: any) => {
    if (!e.over || e.active.id === e.over.id) return;
    const oldI = ids.indexOf(e.active.id);
    const newI = ids.indexOf(e.over.id);
    const reordered = arrayMove(ids, oldI, newI);
    onReorder(reordered);
  };
  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={ids} strategy={horizontalListSortingStrategy}>
        {(() => {
          let cursor = paragraph.timeline_start_sec;
          return paragraph.clips.map((c: Clip) => {
            const left = cursor * pxPerSec;
            const width = Math.max(c.duration_sec * pxPerSec, 40);
            cursor += c.duration_sec;
            return <SortableClip key={c.id} clip={c} left={left} width={width} onClipAction={onClipAction} />;
          });
        })()}
      </SortableContext>
    </DndContext>
  );
}

function SortableClip({ clip, left, width, onClipAction }: any) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: clip.id });
  const style = {
    position: "absolute" as const,
    left, width,
    top: 0, bottom: 8,
    transform: CSS.Translate.toString(transform),
    transition,
    zIndex: isDragging ? 50 : 1,
    opacity: isDragging ? 0.85 : 1,
  };
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <ClipCard clip={clip} onAction={onClipAction} />
    </div>
  );
}
