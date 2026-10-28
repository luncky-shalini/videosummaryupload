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
        Download a YouTube video with client fallback and reliable file resolution.
        """
        os.makedirs(output_dir, exist_ok=True)

        client_profiles = [
            ['web_creator', 'android', 'ios', 'mweb'],
            ['ios', 'android'],
        ]

        last_error = None
        info = None
        filename = None

        for attempt, clients in enumerate(client_profiles, start=1):
            ydl_opts = YouTubeDownloader._build_ydl_opts(
                output_dir,
                player_clients=clients,
            )

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as downloader:
                    info = downloader.extract_info(url, download=True)
                    filename = downloader.prepare_filename(info)

                last_error = None
                break

            except Exception as exc:
                last_error = exc
                error_text = str(exc).lower()

                is_access_error = (
                    "sign in to confirm" in error_text
                    or "confirm you're not a bot" in error_text
                    or "confirm you’re not a bot" in error_text
                    or "403" in error_text
                    or "po token" in error_text
                    or "botguard" in error_text
                )

                if attempt == len(client_profiles) or not is_access_error:
                    break

                logger.warning(
                    "YouTube download attempt %s failed; trying fallback client.",
                    attempt,
                )

        if last_error is not None or info is None:
            error_text = str(last_error or "Unknown YouTube download error")
            lower_error = error_text.lower()

            if (
                "sign in to confirm" in lower_error
                or "confirm you're not a bot" in lower_error
                or "confirm you’re not a bot" in lower_error
                or "botguard" in lower_error
                or "po token" in lower_error
            ):
                raise RuntimeError(
                    "YouTube requires additional verification for this request. "
                    "The configured downloader clients could not access this video. "
                    "Try another publicly accessible video or upload the video file "
                    "directly. If you administer this deployment, check the official "
                    "yt-dlp documentation for supported YouTube authentication "
                    "and PO Token configuration."
                ) from last_error

            raise RuntimeError(
                f"YouTube download failed: {error_text}"
            ) from last_error

        video_id = info.get("id") or "video"

        candidates = []

        if filename:
            candidates.append(filename)

            base = os.path.splitext(filename)[0]
            for ext in (".mp4", ".mkv", ".webm", ".m4a", ".mp3"):
                candidates.append(base + ext)

        candidates.extend(
            glob.glob(os.path.join(output_dir, f"*{video_id}*"))
        )

        actual_filepath = next(
            (
                path for path in candidates
                if os.path.isfile(path)
                and not path.endswith((".part", ".ytdl"))
            ),
            None,
        )

        if not actual_filepath:
            raise RuntimeError(
                "YouTube metadata was retrieved, but the downloaded file "
                "could not be found. Please retry the import."
            )

        return {
            "title": info.get("title", "Imported Video"),
            "duration": float(info.get("duration") or 0.0),
            "filepath": actual_filepath,
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader", "Unknown"),
            "description": info.get("description", ""),
        }
