import os
import subprocess
import json
import math
import logging
from typing import Dict, Any, List, Tuple
from config import settings
from services.ffmpeg_resolver import (
    ensure_ffmpeg,
    get_ffmpeg_path,
    get_ffprobe_path,
    parse_media_metadata_with_ffmpeg
)

logger = logging.getLogger(__name__)


class MediaProcessor:
    @staticmethod
    def get_media_metadata(file_path: str) -> Dict[str, Any]:
        """
        Extracts duration, format, audio/video stream details.
        Uses ffprobe if available; seamlessly falls back to FFmpeg inspect parsing
        to ensure 100% reliable execution in serverless/Vercel environments.
        """
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        # Ensure FFmpeg is available on PATH
        try:
            ffmpeg_bin = ensure_ffmpeg()
        except Exception as e:
            logger.warning(f"FFmpeg resolution failed in get_media_metadata: {e}")
            ffmpeg_bin = "ffmpeg"

        # 1. Try ffprobe (native binary or shim)
        ffprobe_bin = get_ffprobe_path() or "ffprobe"
        cmd = [
            ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            info = json.loads(result.stdout)

            duration = float(info.get("format", {}).get("duration", 0.0))
            size = int(info.get("format", {}).get("size", file_size))

            has_video = any(s.get("codec_type") == "video" for s in info.get("streams", []))
            has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))

            width = None
            height = None
            for s in info.get("streams", []):
                if s.get("codec_type") == "video":
                    width = s.get("width")
                    height = s.get("height")
                    break

            # If duration is valid, return the parsed info
            if duration > 0 or has_video or has_audio:
                return {
                    "duration": duration,
                    "size_bytes": size,
                    "has_video": has_video,
                    "has_audio": has_audio,
                    "width": width,
                    "height": height
                }
        except Exception as e:
            logger.debug(f"ffprobe invocation failed ({e}), falling back to FFmpeg metadata extraction")

        # 2. Fallback: Parse media metadata directly via FFmpeg inspect stderr
        try:
            return parse_media_metadata_with_ffmpeg(file_path, ffmpeg_bin)
        except Exception as e:
            logger.error(f"FFmpeg fallback metadata extraction error: {e}")
            return {
                "duration": 0.0,
                "size_bytes": file_size,
                "has_video": True,
                "has_audio": True,
                "error": str(e)
            }

    @staticmethod
    def extract_audio(input_file: str, output_audio_path: str) -> str:
        """
        Extracts and converts audio to 16kHz mono MP3 at 64k bitrate.
        This provides high intelligibility for Whisper while dramatically reducing file size.
        """
        ffmpeg_bin = get_ffmpeg_path()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", input_file,
            "-vn",                  # Drop video
            "-acodec", "libmp3lame",
            "-ar", "16000",         # 16kHz sample rate
            "-ac", "1",             # Mono
            "-b:a", "64k",          # 64kbps bitrate
            output_audio_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_audio_path

    @staticmethod
    def chunk_audio_if_needed(audio_path: str, max_chunk_size_bytes: int = 24 * 1024 * 1024) -> List[Tuple[str, float]]:
        """
        If audio exceeds max_chunk_size_bytes (~24MB for Groq Whisper limit),
        splits audio into sequential chunks using ffmpeg and returns list of (chunk_path, start_offset_seconds).
        """
        file_size = os.path.getsize(audio_path)
        if file_size <= max_chunk_size_bytes:
            return [(audio_path, 0.0)]

        # Get audio duration
        meta = MediaProcessor.get_media_metadata(audio_path)
        total_duration = meta.get("duration", 0.0)
        if total_duration <= 0:
            return [(audio_path, 0.0)]

        # Determine number of chunks required
        num_chunks = math.ceil(file_size / (max_chunk_size_bytes * 0.8))
        chunk_duration = math.ceil(total_duration / num_chunks)

        chunks = []
        base, ext = os.path.splitext(audio_path)
        ffmpeg_bin = get_ffmpeg_path()

        current_start = 0.0
        idx = 0
        while current_start < total_duration:
            chunk_output = f"{base}_chunk_{idx}{ext}"
            duration_to_cut = min(chunk_duration, total_duration - current_start)

            cmd = [
                ffmpeg_bin,
                "-y",
                "-ss", str(current_start),
                "-t", str(duration_to_cut),
                "-i", audio_path,
                "-c", "copy",
                chunk_output
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            chunks.append((chunk_output, current_start))

            current_start += duration_to_cut
            idx += 1

        return chunks

    @staticmethod
    def extract_keyframes(video_path: str, output_dir: str, interval_seconds: int = 60, max_frames: int = 10) -> List[str]:
        """
        Samples video frames at regular intervals for visual/slide inspection.
        """
        os.makedirs(output_dir, exist_ok=True)
        meta = MediaProcessor.get_media_metadata(video_path)
        duration = meta.get("duration", 0.0)

        if not meta.get("has_video") or duration <= 0:
            return []

        frame_paths = []
        step = max(interval_seconds, int(duration / max_frames)) if duration > max_frames * interval_seconds else interval_seconds

        ffmpeg_bin = get_ffmpeg_path()
        curr = step
        count = 0
        while curr < duration and count < max_frames:
            frame_file = os.path.join(output_dir, f"frame_{count:03d}.jpg")
            cmd = [
                ffmpeg_bin,
                "-y",
                "-ss", str(curr),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "3",
                frame_file
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                if os.path.exists(frame_file):
                    frame_paths.append(frame_file)
            except Exception:
                pass
            curr += step
            count += 1

        return frame_paths
