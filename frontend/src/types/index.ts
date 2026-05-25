export type ClipSource = "youtube" | "pexels" | "upload";
export type ProjectStatus =
  | "queued" | "generating_script" | "generating_tts" | "searching" | "matching"
  | "downloading" | "normalizing" | "ready" | "rendering" | "rendered" | "error";

export interface Clip {
  id: string;
  source: ClipSource;
  file_path: string;
  thumbnail_path: string | null;
  duration_sec: number;
  paragraph_id: number;
  order_in_paragraph: number;
  visual_description: string | null;
  match_quality: number | null;
  yt_video_id: string | null;
  yt_channel: string | null;
  yt_video_title: string | null;
  yt_video_url: string | null;
  yt_start_sec: number | null;
  yt_end_sec: number | null;
  pexels_id: string | null;
  pexels_url: string | null;
  pexels_query: string | null;
  upload_filename: string | null;
}

export interface Sentence {
  id: string;
  text: string;
  start_sec: number;
  end_sec: number;
  paragraph_id: number;
}

export interface Paragraph {
  id: number;
  text: string;
  audio_path: string;
  audio_duration_sec: number;
  timeline_start_sec: number;
  sentences: Sentence[];
  clips: Clip[];
  search_queries: string[];
}

export interface Project {
  id: string;
  prompt: string;
  title: string;
  status: ProjectStatus;
  progress: number;
  progress_message: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  full_audio_path: string | null;
  full_subtitles_path: string | null;
  final_video_path: string | null;
  paragraphs: Paragraph[];
}
