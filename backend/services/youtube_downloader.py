import os
import glob
import logging
import shutil
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
    def _resolve_js_runtime() -> Optional[Dict[str, Dict[str, str]]]:
        """
        Discovers a JavaScript challenge solving runtime (Node.js, Deno, Bun)
        supported by yt-dlp to solve YouTube signature/deobfuscation challenges.
        """
        # 1. Custom configured runtime path
        if settings.YOUTUBE_JS_RUNTIME_PATH and os.path.exists(settings.YOUTUBE_JS_RUNTIME_PATH):
            return {"node": {"path": os.path.abspath(settings.YOUTUBE_JS_RUNTIME_PATH)}}

        # 2. Check for node or nodejs on system PATH
        node_bin = shutil.which("node") or shutil.which("nodejs")
        if node_bin:
            return {"node": {"path": node_bin}}

        # 3. Check for deno or bun on system PATH
        deno_bin = shutil.which("deno")
        if deno_bin:
            return {"deno": {"path": deno_bin}}

        bun_bin = shutil.which("bun")
        if bun_bin:
            return {"bun": {"path": bun_bin}}

        return None

    @staticmethod
    def _build_ydl_opts(output_dir: str, player_clients: list = None) -> Dict[str, Any]:
        """
        Constructs robust yt-dlp options with multi-client player rotation,
        format fallback, PO token integration, and serverless FFmpeg path binding.
        """
        outtmpl = os.path.join(output_dir, "%(id)s.%(ext)s")
        clients = player_clients or ['web_creator', 'mweb', 'android', 'ios']

        # Ensure FFmpeg is available and locate its directory for yt-dlp muxing
        ffmpeg_location = None
        try:
            ensure_ffmpeg()
            ffmpeg_location = get_ffmpeg_dir()
        except Exception as e:
            logger.warning(f"FFmpeg not available for YouTubeDownloader: {e}")

        youtube_extractor_args: Dict[str, Any] = {
            'player_client': clients
        }

        # Inject PO Token if configured
        if settings.YOUTUBE_PO_TOKEN and settings.YOUTUBE_PO_TOKEN.strip():
            youtube_extractor_args['po_token'] = [settings.YOUTUBE_PO_TOKEN.strip()]

        # Inject Visitor Data if configured
        if settings.YOUTUBE_VISITOR_DATA and settings.YOUTUBE_VISITOR_DATA.strip():
            youtube_extractor_args['visitor_data'] = [settings.YOUTUBE_VISITOR_DATA.strip()]

        opts = {
            # Format selection: prefer 720p MP4 or high quality audio with fallback to best single stream
            'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/bestvideo[height<=720]+bestaudio/best[height<=720]/bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'merge_output_format': 'mp4',
            'retries': 3,
            'extractor_args': {
                'youtube': youtube_extractor_args
            }
        }

        # Configure official bgutil PO Token provider plugin if provider URL is configured
        if settings.YOUTUBE_POT_PROVIDER_URL and settings.YOUTUBE_POT_PROVIDER_URL.strip():
            opts['extractor_args']['youtubepot-bgutilhttp'] = {
                'base_url': [settings.YOUTUBE_POT_PROVIDER_URL.strip()]
            }
        else:
            # Disable plugins when no POT provider URL is set to avoid the socket timeout on http://127.0.0.1:4416/ping
            opts['no_plugins'] = True

        # Configure JS challenge solver if runtime is discovered
        js_runtimes = YouTubeDownloader._resolve_js_runtime()
        if js_runtimes:
            opts['js_runtimes'] = js_runtimes

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
    def download_via_worker(url: str, user_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Delegates YouTube download to an external persistent worker service
        capable of solving PO Token challenges or hosting bgutil-provider.
        """
        import httpx

        worker_url = settings.YOUTUBE_WORKER_URL.rstrip("/")
        headers = {}
        if settings.YOUTUBE_WORKER_SECRET and settings.YOUTUBE_WORKER_SECRET.strip():
            secret = settings.YOUTUBE_WORKER_SECRET.strip()
            headers["X-Worker-Key"] = secret
            headers["Authorization"] = f"Bearer {secret}"

        endpoint = f"{worker_url}/api/worker/download"
        payload = {
            "url": url,
            "user_id": user_id,
            "title": title
        }

        logger.info(f"Delegating YouTube import for {url} to external worker: {worker_url}")

        try:
            with httpx.Client(timeout=180.0) as client:
                res = client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise RuntimeError(
                f"External YouTube worker at {worker_url} timed out processing {url}. "
                "The video may be too large or the worker is overloaded. Try uploading the video file directly."
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to connect to external YouTube worker at {worker_url}: {str(e)}. "
                "Please verify that the worker service is running and accessible."
            )

        if res.status_code in (401, 403):
            raise RuntimeError(
                "External YouTube worker authentication failed. "
                "Please verify that YOUTUBE_WORKER_SECRET matches on both the backend and worker."
            )

        if res.status_code != 200:
            error_detail = "Unknown error"
            try:
                error_detail = res.json().get("detail", res.text)
            except Exception:
                error_detail = res.text
            raise RuntimeError(f"External YouTube worker failed: {error_detail}")

        data = res.json()
        return {
            "title": data.get("title", "Imported Video"),
            "duration": float(data.get("duration", 0.0)),
            "filepath": None,
            "storage_path": data.get("storage_path"),
            "file_size_bytes": data.get("file_size_bytes", 0),
            "thumbnail": data.get("thumbnail"),
            "uploader": data.get("uploader", "Unknown"),
            "description": data.get("description", ""),
        }

    @staticmethod
    def _extract_and_download_in_process(url: str, output_dir: str) -> Dict[str, Any]:
        """
        Executes local in-process yt-dlp download across configured client profiles.
        """
        os.makedirs(output_dir, exist_ok=True)

        client_profiles = [
            ['android', 'ios'],
            ['tv'],
            ['web_creator', 'mweb', 'android', 'ios'],
            ['web', 'default'],
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
                    or "no video formats found" in error_text
                    or "sabr" in error_text
                    or "requested format is not available" in error_text
                )

                if attempt == len(client_profiles) or not is_access_error:
                    break

                logger.warning(
                    "YouTube download attempt %s failed (%s); trying fallback client profile %s.",
                    attempt,
                    exc,
                    attempt + 1,
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
                    "YouTube requires additional verification (bot detection) for this video from the server's network. "
                    "The current serverless deployment cannot solve this challenge without an external worker or session credentials. "
                    "You can: "
                    "1. Upload the video file directly (drag & drop above) — video upload works globally. "
                    "2. Configure an external downloader worker via YOUTUBE_WORKER_URL and YOUTUBE_WORKER_SECRET. "
                    "3. Configure YOUTUBE_COOKIES_CONTENT in your deployment environment variables."
                ) from last_error

            if "403" in lower_error or "forbidden" in lower_error:
                raise RuntimeError(
                    "YouTube returned HTTP 403 Forbidden. Access to this video or format is restricted "
                    "by YouTube. Please try another video or upload the video file directly."
                ) from last_error

            if "unavailable" in lower_error or "private" in lower_error or "age" in lower_error:
                raise RuntimeError(
                    "This YouTube video is restricted or unavailable (it may be private, age-restricted, or removed). "
                    "Please verify the URL or upload the video file directly."
                ) from last_error

            if "429" in lower_error or "too many requests" in lower_error:
                raise RuntimeError(
                    "YouTube returned HTTP 429 (Too Many Requests). The server is temporarily rate-limited by YouTube. "
                    "Please try again shortly or upload the video file directly."
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

    @staticmethod
    def extract_and_download(
        url: str,
        output_dir: str,
        user_id: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Download a YouTube video. If an external worker is configured (e.g. for Vercel production),
        delegates to the worker service to handle PO token generation and datacenter IP bypass.
        Otherwise executes local in-process download.
        """
        if settings.YOUTUBE_WORKER_URL and settings.YOUTUBE_WORKER_URL.strip():
            return YouTubeDownloader.download_via_worker(url, user_id=user_id or "shared", title=title)

        return YouTubeDownloader._extract_and_download_in_process(url, output_dir)
