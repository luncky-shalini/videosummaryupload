import os
import glob
import logging
import yt_dlp
from typing import Dict, Any
from services.ffmpeg_resolver import ensure_ffmpeg, get_ffmpeg_dir

logger = logging.getLogger(__name__)


class YouTubeDownloader:
    @staticmethod
    def extract_and_download(url: str, output_dir: str) -> Dict[str, Any]:
        """
        Downloads the best audio stream or lightweight video from a URL using yt-dlp.
        Returns dict with title, duration, output_filepath, thumbnail.
        Handles YouTube, Shorts, mobile links, and various formats reliably.
        Configures ffmpeg_location so yt-dlp can locate the static FFmpeg binary in serverless environments.
        """
        os.makedirs(output_dir, exist_ok=True)
        outtmpl = os.path.join(output_dir, "%(id)s.%(ext)s")

        # Ensure FFmpeg is available and locate its directory for yt-dlp muxing
        ffmpeg_location = None
        try:
            ensure_ffmpeg()
            ffmpeg_location = get_ffmpeg_dir()
        except Exception as e:
            logger.warning(f"FFmpeg not available for YouTubeDownloader: {e}")

        ydl_opts = {
            # Prefer MP4 container with max 720p for rapid processing and streaming
            'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'merge_output_format': 'mp4',
            'retries': 3,
        }

        if ffmpeg_location:
            ydl_opts['ffmpeg_location'] = ffmpeg_location

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            video_id = info.get("id") or "video"

            # 1. Check exact prepared filename
            actual_filepath = filename
            if not os.path.exists(actual_filepath):
                # 2. Check with .mp4 extension
                base = filename.rsplit(".", 1)[0]
                for ext in [".mp4", ".mkv", ".webm", ".m4a", ".mp3"]:
                    if os.path.exists(base + ext):
                        actual_filepath = base + ext
                        break

            # 3. Fallback: Search output directory by video ID
            if not os.path.exists(actual_filepath) and video_id:
                candidates = glob.glob(os.path.join(output_dir, f"*{video_id}*"))
                for c in candidates:
                    if not c.endswith(".part") and os.path.isfile(c):
                        actual_filepath = c
                        break

            return {
                "title": info.get("title", "Imported Video"),
                "duration": float(info.get("duration", 0.0)),
                "filepath": actual_filepath,
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader", "Unknown"),
                "description": info.get("description", "")
            }
