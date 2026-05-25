"""ffmpeg normalize, concat, mux. Adapted from v3 pipeline."""
from __future__ import annotations
import subprocess
import re
from pathlib import Path

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def probe_duration(path: Path) -> float:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            text=True, timeout=10,
        ).strip()
        return float(out) if out else 0.0
    except Exception:
        return 0.0

def normalize_clip(src: Path, dst: Path, attribution: str | None = None) -> bool:
    """Normalize to 1920x1080 H.264 30fps no audio. Optional attribution overlay."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30"
    if attribution:
        clean = re.sub(r"[^\w\s&.\-]", "", attribution)[:60]
        vf += (
            f",drawtext=fontfile={FONT_BOLD}:text='{clean}':fontcolor=white:fontsize=22:"
            f"x=w-tw-30:y=h-th-25:box=1:boxcolor=black@0.45:boxborderw=8"
        )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-crf", "23",
        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart",
        str(dst),
    ]
    try:
        subprocess.check_call(cmd, timeout=40)
        return dst.exists() and dst.stat().st_size > 10_000
    except Exception:
        return False

def trim_clip(src: Path, dst: Path, duration: float) -> bool:
    """Trim a normalized clip to an exact duration."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "0", "-t", f"{duration:.3f}", "-i", str(src),
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-crf", "23",
        "-pix_fmt", "yuv420p", "-vf", "fps=30", "-an", "-movflags", "+faststart",
        str(dst),
    ]
    try:
        subprocess.check_call(cmd, timeout=30)
        return dst.exists()
    except Exception:
        return False

def thumbnail(src: Path, dst: Path, t: float = 1.0) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.check_call([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(t), "-i", str(src), "-frames:v", "1", "-q:v", "3",
            "-vf", "scale=480:270:force_original_aspect_ratio=increase,crop=480:270",
            str(dst),
        ], timeout=10)
        return dst.exists()
    except Exception:
        return False

def concat_audio(parts: list[Path], dst: Path) -> bool:
    listfile = dst.with_suffix(".list")
    listfile.write_text("\n".join(f"file '{p.resolve()}'" for p in parts))
    try:
        subprocess.check_call([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listfile),
            "-c", "copy", str(dst),
        ], timeout=60)
        return dst.exists()
    except Exception:
        return False

def concat_video(parts: list[Path], dst: Path) -> bool:
    listfile = dst.with_suffix(".list")
    listfile.write_text("\n".join(f"file '{p.resolve()}'" for p in parts))
    try:
        subprocess.check_call([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-f", "concat", "-safe", "0", "-i", str(listfile),
            "-c", "copy", str(dst),
        ], timeout=60)
        return dst.exists()
    except Exception:
        return False

def final_mux(silent_video: Path, audio: Path, dst: Path, bgm: Path | None = None, subtitles: Path | None = None) -> bool:
    inputs = ["-i", str(silent_video), "-i", str(audio)]
    map_v = "0:v:0"
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", str(bgm)]
        fc = "[2:a]volume=0.10[bgm];[1:a]volume=1.0[v];[v][bgm]amix=inputs=2:duration=longest:dropout_transition=2[mix];[mix]loudnorm=I=-14:TP=-1:LRA=11[aout]"
        map_a = "[aout]"
    else:
        fc = "[1:a]loudnorm=I=-14:TP=-1:LRA=11[aout]"
        map_a = "[aout]"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        *inputs,
        "-filter_complex", fc,
        "-map", map_v, "-map", map_a,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
        "-shortest", "-movflags", "+faststart",
    ]
    if subtitles:
        cmd = cmd[:cmd.index("-shortest")] + ["-i", str(subtitles), "-map", str(len(inputs)//2), "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"] + cmd[cmd.index("-shortest"):]
    cmd.append(str(dst))
    try:
        subprocess.check_call(cmd, timeout=60)
        return dst.exists()
    except Exception:
        return False
