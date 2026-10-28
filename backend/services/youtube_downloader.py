import os
import glob
import logging
import tempfile
import yt_dlp
from typing import Dict, Any, Optional
from config import settings
from services.ffmpeg_resolver import ensure_ffmpeg, get_ffmpeg_dir

logger = logging.getLogger(__name__)


class YouTubeDownloader:
    @staticmethod
    def _resolve_cookiefile() -> Optional[str]:
        """
        Resolves cookie file path from settings or environment.
        Supports YOUTUBE_COOKIES_PATH, inline YOUTUBE_COOKIES_CONTENT
        (written to /tmp/yt_cookies.txt for serverless), and local cookies.txt.
        """
        # 1. Configured file path
        if settings.YOUTUBE_COOKIES_PATH and os.path.exists(settings.YOUTUBE_COOKIES_PATH):
            return os.path.abspath(settings.YOUTUBE_COOKIES_PATH)

        # 2. Inline cookie content passed via environment variable (ideal for Vercel secrets)
        if settings.YOUTUBE_COOKIES_CONTENT and settings.YOUTUBE_COOKIES_CONTENT.strip():
            tmp_cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
            try:
                with open(tmp_cookie_path, "w", encoding="utf-8") as f:
                    f.write(settings.YOUTUBE_COOKIES_CONTENT.strip())
                return tmp_cookie_path
            except Exception as e:
                logger.warning(f"Failed to write inline YouTube cookies: {e}")

        # 3. Check for cookies.txt in common repository locations
        for candidate in ["cookies.txt", "backend/cookies.txt", "../cookies.txt"]:
            if os.path.exists(candidate):
                return os.path.abspath(candidate)

        return None

    @staticmethod
    def _build_ydl_opts(output_dir: str, player_clients: list = None) -> Dict[str, Any]:
        """
        Constructs robust yt-dlp options with multi-client player rotation,
        format fallback, and serverless FFmpeg path binding.
        """
        outtmpl = os.path.join(output_dir, "%(id)s.%(ext)s")
        clients = player_clients or ['web_creator', 'android', 'ios', 'mweb']

        # Ensure FFmpeg is available and locate its directory for yt-dlp muxing
        ffmpeg_location = None
        try:
            ensure_ffmpeg()
            ffmpeg_location = get_ffmpeg_dir()
        except Exception as e:
            logger.warning(f"FFmpeg not available for YouTubeDownloader: {e}")

        opts = {
            # Format selection: prefer 720p MP4 or high quality audio with fallback to best single stream
            'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]/bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'merge_output_format': 'mp4',
            'retries': 3,
            'extractor_args': {
                'youtube': {
                    'player_client': clients
                }
            }
        }

        if ffmpeg_location:
            opts['ffmpeg_location'] = ffmpeg_location

        cookiefile = YouTubeDownloader._resolve_cookiefile()
        if cookiefile:
            opts['cookiefile'] = cookiefile
            logger.info(f"Using YouTube cookie file at: {cookiefile}")

        if settings.YOUTUBE_PROXY:
            opts['proxy'] = settings.YOUTUBE_PROXY

        return opts

    @staticmethod
    def extract_and_download(url: str, output_dir: str) -> Dict[str, Any]:
        """
        Downloads the best audio stream or lightweight video from a URL using yt-dlp.
        Returns dict with title, duration, output_filepath, thumbnail.
        Handles YouTube, Shorts, mobile links, and various formats reliably.
        Rotates player clients (web_creator, android, ios, mweb) to bypass YouTube bot detection.
        """
        os.makedirs(output_dir, exist_ok=True)

        ydl_opts = YouTubeDownloader._build_ydl_opts(output_dir)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as primary_err:
            err_str = str(primary_err)
            # If flagged with bot check, attempt fallback with alternative client profile (e.g. android only)
            if "Sign in to confirm you’re not a bot" in err_str or "confirm you're not a bot" in err_str or "403" in err_str:
                logger.warning(f"Primary YouTube client flagged by bot check, trying fallback client: {primary_err}")
                fallback_opts = YouTubeDownloader._build_ydl_opts(output_dir, player_clients=['android', 'ios'])
                try:
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl_fallback:
                        info = ydl_fallback.extract_info(url, download=True)
                except Exception as fallback_err:
                    raise RuntimeError(
                        f"YouTube blocked this request with bot verification. "
                        f"To resolve on serverless environments, provide YouTube cookies via the "
                        f"YOUTUBE_COOKIES_CONTENT or YOUTUBE_COOKIES_PATH environment secret, "
                        f"or upload the video file directly. Details: {str(fallback_err)}"
                    ) from fallback_err
            else:
                raise primary_err

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
