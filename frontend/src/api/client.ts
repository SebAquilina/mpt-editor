import type { Project, Clip } from "../types";

const API = "";  // proxied via Vite -> :8000

async function jget<T>(path: string): Promise<T> {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
async function jpost<T>(path: string, body?: any): Promise<T> {
  const r = await fetch(API + path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
async function jput<T>(path: string, body?: any): Promise<T> {
  const r = await fetch(API + path, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
async function jdel(path: string): Promise<void> {
  const r = await fetch(API + path, { method: "DELETE" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
}

export const api = {
  createProject: (prompt: string) => jpost<{ project_id: string }>("/api/projects", { prompt }),
  getProject: (id: string) => jget<Project>(`/api/projects/${id}`),
  listProjects: () => jget<Project[]>("/api/projects"),
  deleteProject: (id: string) => jdel(`/api/projects/${id}`),

  reorderClips: (projectId: string, paragraph_id: number, ordered_clip_ids: string[]) =>
    jpost(`/api/projects/${projectId}/clips/reorder`, { paragraph_id, ordered_clip_ids }),
  getAlternates: (projectId: string, clipId: string) =>
    jpost<{ alternates: Clip[] }>(`/api/projects/${projectId}/clips/${clipId}/alternates`),
  searchReplace: (projectId: string, clipId: string, query: string, source: "youtube"|"pexels"|"both" = "both") =>
    jpost<{ results: Clip[] }>(`/api/projects/${projectId}/clips/${clipId}/search`, { query, source }),
  replaceClip: (projectId: string, clipId: string, new_clip_id: string) =>
    jput(`/api/projects/${projectId}/clips/${clipId}`, { new_clip_id }),
  uploadReplacement: (projectId: string, clipId: string, file: File) => {
    const fd = new FormData(); fd.append("file", file);
    return fetch(`/api/projects/${projectId}/clips/${clipId}/upload`, { method: "POST", body: fd })
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); });
  },
  deleteClip: (projectId: string, clipId: string) =>
    jdel(`/api/projects/${projectId}/clips/${clipId}`),

  render: (projectId: string) => jpost<{ render_id: string; video_url: string }>(`/api/projects/${projectId}/render`),
  fileUrl: (path: string) => `/api/files/${path}`,

  // ─── Settings (runtime API key management) ─────────────────────────────────
  getKeys: () => jget<{gemini_configured: boolean; pexels_configured: boolean; gemini_masked: string | null; pexels_masked: string | null}>("/api/settings/keys"),
  updateKeys: (gemini_api_key?: string, pexels_api_key?: string) =>
    jput<{gemini_configured: boolean; pexels_configured: boolean}>("/api/settings/keys", { gemini_api_key, pexels_api_key }),

  // ─── Materialize search result before swapping into editor ────────────────
  materializeClip: (projectId: string, clipId: string, source: "youtube" | "pexels", spec: any) =>
    jpost<Clip>(`/api/projects/${projectId}/clips/${clipId}/materialize`, { source, ...spec }),

  // ─── Render history ──────────────────────────────────────────────────────
  listRenders: (projectId: string) =>
    jget<{renders: any[]}>(`/api/projects/${projectId}/renders`),
  resumeRender: (projectId: string, renderId: string) =>
    jpost(`/api/projects/${projectId}/render/${renderId}/resume`),
};

export function subscribeEvents(projectId: string, onEvent: (ev: any) => void): () => void {
  const es = new EventSource(`/api/projects/${projectId}/events`);
  const handler = (e: MessageEvent) => {
    try { onEvent(JSON.parse(e.data)); } catch {}
  };
  es.addEventListener("progress", handler as any);
  es.addEventListener("snapshot", handler as any);
  es.addEventListener("render_progress", handler as any);
  es.addEventListener("render_done", handler as any);
  es.addEventListener("render_error", handler as any);
  es.addEventListener("done", () => { es.close(); onEvent({ type: "done" }); });
  es.addEventListener("error", () => es.close());
  return () => es.close();
}
