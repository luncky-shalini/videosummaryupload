import os
import yt_dlp
from typing import Dict, Any

class YouTubeDownloader:
    @staticmethod
    def extract_and_download(url: str, output_dir: str) -> Dict[str, Any]:
        """
        Downloads the best audio stream or lightweight video from a URL using yt-dlp.
        Returns dict with title, duration, output_filepath, thumbnail.
        """
        os.makedirs(output_dir, exist_ok=True)
        outtmpl = os.path.join(output_dir, "%(id)s.%(ext)s")
        
        ydl_opts = {
            # Prefer MP4 format with audio and video (max 720p to save bandwidth/disk)
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'merge_output_format': 'mp4',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not filename.endswith(".mp4") and os.path.exists(filename.rsplit(".", 1)[0] + ".mp4"):
                filename = filename.rsplit(".", 1)[0] + ".mp4"
                
            return {
                "title": info.get("title", "Imported Video"),
                "duration": float(info.get("duration", 0.0)),
                "filepath": filename,
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader", "Unknown"),
                "description": info.get("description", "")
            }
