from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FPS = 30
WIDTH = 1920
HEIGHT = 1080
MIN_SEGMENT = 2.2
MAX_SEGMENT = 4.8


def _decode_output(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk", sys.getdefaultencoding()):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run(cmd: list[str]) -> None:
    completed = subprocess.run(cmd, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{_decode_output(completed.stdout)}\nSTDERR:\n{_decode_output(completed.stderr)}"
        )


def run_output(cmd: list[str]) -> str:
    completed = subprocess.run(cmd, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{_decode_output(completed.stdout)}\nSTDERR:\n{_decode_output(completed.stderr)}"
        )
    return _decode_output(completed.stdout).strip()


def ffprobe_duration(path: Path) -> float:
    output = run_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(output)


def list_video_files(clips_dir: Path) -> list[Path]:
    items = []
    for ext in ("*.mp4", "*.mov", "*.m4v", "*.webm"):
        items.extend(sorted(clips_dir.glob(ext)))
    return items


def read_text(text_file: Path) -> str:
    return text_file.read_text(encoding="utf-8").strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])", text.replace("\r", ""))
    cleaned = [part.strip() for part in parts if part.strip()]
    return cleaned or [text]


def estimate_segments(total_duration: float, clip_count: int) -> int:
    ideal = max(4, math.ceil(total_duration / 3.2))
    return max(4, min(max(clip_count, 1) * 2, ideal))


def choose_font() -> str:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("No supported Chinese font found in C:\\Windows\\Fonts")


def generate_voice(text: str, audio_path: Path, voice: str) -> None:
    run(
        [
            "edge-tts",
            "--voice",
            voice,
            "--text",
            text,
            "--write-media",
            str(audio_path),
        ]
    )


def normalize_clip(src: Path, dest: Path, start: float, duration: float) -> None:
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.2f}",
            "-t",
            f"{duration:.2f}",
            "-i",
            str(src),
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            str(dest),
        ]
    )


def build_segments(video_files: list[Path], audio_duration: float, temp_dir: Path) -> list[Path]:
    unique_count = len({path.resolve() for path in video_files})
    if unique_count < 4:
        raise RuntimeError(
            "Need at least 4 distinct dynamic clips. Refuse to render repetitive video."
        )

    segment_count = estimate_segments(audio_duration, len(video_files))
    segment_duration = max(MIN_SEGMENT, min(MAX_SEGMENT, audio_duration / segment_count))
    segments: list[Path] = []
    usage_counts: dict[Path, int] = {path: 0 for path in video_files}
    sequence: list[Path] = []
    for index in range(segment_count):
        candidates = sorted(
            video_files,
            key=lambda path: (
                usage_counts[path],
                1 if sequence and path == sequence[-1] else 0,
                str(path),
            ),
        )
        src = None
        for candidate in candidates:
            if sequence and candidate == sequence[-1]:
                continue
            if usage_counts[candidate] >= 2:
                continue
            src = candidate
            break
        if src is None:
            fallback = [candidate for candidate in candidates if not sequence or candidate != sequence[-1]]
            if not fallback:
                raise RuntimeError("Unable to build non-repetitive clip sequence.")
            src = fallback[0]

        src_duration = ffprobe_duration(src)
        usable = max(segment_duration, min(src_duration, MAX_SEGMENT))
        start_max = max(src_duration - usable - 0.1, 0.0)
        start = 0.0 if start_max == 0 else (index * 1.37) % start_max
        dest = temp_dir / f"segment_{index:02d}.mp4"
        normalize_clip(src, dest, start, min(usable, audio_duration))
        segments.append(dest)
        sequence.append(src)
        usage_counts[src] += 1
    return segments


def concat_segments(segments: list[Path], output_path: Path) -> None:
    concat_file = output_path.parent / "segments.txt"
    concat_file.write_text(
        "".join(f"file '{segment.as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_path),
        ]
    )


def format_ass_time(seconds: float) -> str:
    centis = int(round(seconds * 100))
    hours = centis // 360000
    minutes = (centis % 360000) // 6000
    secs = (centis % 6000) // 100
    cs = centis % 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def wrap_text(text: str, width: int) -> str:
    lines: list[str] = []
    current = ""
    for char in text:
        current += char
        if len(current) >= width:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return "\\N".join(lines[:2])


def ffmpeg_filter_path(path: Path) -> str:
    return path.as_posix().replace(":", "\\:").replace(",", "\\,")


def make_ass(title: str, hook: str, narration: str, audio_duration: float, ass_path: Path) -> None:
    sentences = split_sentences(narration)
    total_units = sum(max(len(s), 8) for s in sentences)
    current = 0.0
    events = []
    for sentence in sentences:
        units = max(len(sentence), 8)
        duration = max(1.4, audio_duration * units / total_units)
        start = current
        end = min(audio_duration, current + duration)
        text = wrap_text(sentence, 12)
        events.append(
            f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Body,,0,0,0,,{text}"
        )
        current = end

    title_end = min(3.6, audio_duration)
    title_text = wrap_text(title, 10)
    hook_text = wrap_text(hook, 12)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Hook,Microsoft YaHei,56,&H00FFFFFF,&H0000C8FF,&H00000000,&H5A101010,-1,0,0,0,100,100,0,0,3,3,0,8,88,120,100,1
Style: Title,Microsoft YaHei,78,&H00FFFFFF,&H0000C8FF,&H00000000,&H4A000000,-1,0,0,0,100,100,0,0,3,4,0,8,88,280,190,1
Style: Body,Microsoft YaHei,60,&H00FFFFFF,&H0030D5FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,3,3,0,2,120,120,120,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
Dialogue: 0,0:00:00.00,{format_ass_time(title_end)},Hook,,0,0,0,,{{\\pos(370,150)}}{hook_text}
Dialogue: 0,0:00:00.00,{format_ass_time(title_end)},Title,,0,0,0,,{{\\pos(420,265)}}{title_text}
"""
    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def mux_video(video_path: Path, audio_path: Path, ass_path: Path, output_path: Path, font_path: str) -> None:
    subtitle_filter = (
        f"subtitles=filename='{ffmpeg_filter_path(ass_path)}':"
        f"fontsdir='{ffmpeg_filter_path(Path(font_path).parent)}'"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-vf",
            subtitle_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "19",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_path),
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a dynamic silver-content video.")
    parser.add_argument("--title", required=True, help="Primary title shown in the opening seconds.")
    parser.add_argument("--hook", required=True, help="Short hook text for the first screen.")
    parser.add_argument("--speech-file", required=True, help="Path to UTF-8 text file for narration.")
    parser.add_argument("--clips-dir", required=True, help="Directory of real dynamic stock or shot clips.")
    parser.add_argument("--output", required=True, help="Final mp4 path.")
    parser.add_argument("--voice", default="zh-CN-XiaoxiaoNeural", help="edge-tts voice name.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    speech_file = Path(args.speech_file)
    clips_dir = Path(args.clips_dir)
    output_path = Path(args.output)

    if not speech_file.exists():
        raise FileNotFoundError(f"Speech file not found: {speech_file}")
    if not clips_dir.exists():
        raise FileNotFoundError(f"Clips directory not found: {clips_dir}")

    video_files = list_video_files(clips_dir)
    if not video_files:
        raise RuntimeError("No real dynamic clip files found. Refuse to build slideshow video.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    narration = read_text(speech_file)
    font_path = choose_font()

    with tempfile.TemporaryDirectory(prefix="silver_video_") as temp_raw:
        temp_dir = Path(temp_raw)
        audio_path = temp_dir / "voice.mp3"
        stitched_path = temp_dir / "stitched.mp4"
        final_base_path = temp_dir / "base.mp4"
        ass_path = temp_dir / "subtitles.ass"

        generate_voice(narration, audio_path, args.voice)
        audio_duration = ffprobe_duration(audio_path)
        segments = build_segments(video_files, audio_duration, temp_dir)
        concat_segments(segments, stitched_path)
        shutil.copy2(stitched_path, final_base_path)
        make_ass(args.title, args.hook, narration, audio_duration, ass_path)
        mux_video(final_base_path, audio_path, ass_path, output_path, font_path)

    result = {
        "output": str(output_path),
        "voice": args.voice,
        "clip_count": len(video_files),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise
