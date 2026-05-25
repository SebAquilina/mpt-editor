import { useEffect, useRef } from "react";

interface Props {
  audioUrl: string | null;
  videoUrl?: string | null;
  playing: boolean;
  playhead: number;
  onTimeUpdate: (t: number) => void;
  onEnded: () => void;
}

export function PreviewPlayer({ audioUrl, videoUrl, playing, playhead, onTimeUpdate, onEnded }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const a = audioRef.current; const v = videoRef.current;
    if (a) {
      if (playing) a.play().catch(() => {});
      else a.pause();
    }
    if (v) {
      if (playing) v.play().catch(() => {});
      else v.pause();
    }
  }, [playing]);

  useEffect(() => {
    const a = audioRef.current; const v = videoRef.current;
    if (a && Math.abs(a.currentTime - playhead) > 0.5) a.currentTime = playhead;
    if (v && Math.abs(v.currentTime - playhead) > 0.5) v.currentTime = playhead;
  }, [playhead]);

  return (
    <div className="bg-bg border border-border rounded-xl overflow-hidden aspect-video relative">
      {videoUrl ? (
        <video ref={videoRef} src={videoUrl} className="w-full h-full" controls
               onTimeUpdate={(e) => onTimeUpdate((e.target as HTMLVideoElement).currentTime)}
               onEnded={onEnded} />
      ) : (
        <>
          {audioUrl && (
            <audio ref={audioRef} src={audioUrl}
                   onTimeUpdate={(e) => onTimeUpdate((e.target as HTMLAudioElement).currentTime)}
                   onEnded={onEnded} />
          )}
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500">
            <div className="text-6xl mb-3">🎬</div>
            <p>Click Render to assemble preview</p>
          </div>
        </>
      )}
    </div>
  );
}
