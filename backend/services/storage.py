import os
import mimetypes
import logging
from typing import Optional
from fastapi.responses import FileResponse, RedirectResponse
from config import settings, ensure_upload_dir
from database import get_supabase_admin

logger = logging.getLogger(__name__)

class StorageService:
    @staticmethod
    def upload_file(local_path: str, user_id: str, filename: str) -> str:
        """
        Stores media file in Supabase Storage or local storage based on MEDIA_STORAGE_TYPE.
        Returns the persistent storage path (e.g. supabase://media-vault/user_id/filename or local path).
        """
        if settings.MEDIA_STORAGE_TYPE == "supabase":
            bucket = settings.STORAGE_BUCKET_NAME
            object_path = f"{user_id}/{filename}"
            content_type, _ = mimetypes.guess_type(local_path)
            content_type = content_type or "video/mp4"

            try:
                supabase = get_supabase_admin()
                with open(local_path, "rb") as f:
                    file_bytes = f.read()

                # Upload to Supabase Storage bucket
                supabase.storage.from_(bucket).upload(
                    path=object_path,
                    file=file_bytes,
                    file_options={"content-type": content_type, "upsert": "true"}
                )
                logger.info(f"Uploaded media to Supabase Storage: {bucket}/{object_path}")
                return f"supabase://{bucket}/{object_path}"
            except Exception as e:
                logger.error(f"Failed to upload to Supabase Storage, falling back to local path: {e}")
                return local_path

        return local_path

    @staticmethod
    def get_stream_response(video: dict, user_id: str):
        """
        Returns a FileResponse for local media playback with HTTP Range support,
        or a 307 RedirectResponse to a signed Supabase Storage URL for persistent cloud playback.
        """
        filepath = video.get("storage_path") or ""
        
        # 1. Local file playback if media file exists on disk
        if filepath and not filepath.startswith("supabase://") and os.path.exists(filepath):
            media_type, _ = mimetypes.guess_type(filepath)
            if not media_type:
                media_type = "video/mp4" if filepath.endswith((".mp4", ".m4v")) else "application/octet-stream"

            return FileResponse(
                filepath,
                media_type=media_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Disposition": f'inline; filename="{os.path.basename(filepath)}"'
                }
            )

        # 2. Supabase Storage playback: generate signed streaming URL
        bucket = settings.STORAGE_BUCKET_NAME
        object_path = ""
        if filepath.startswith(f"supabase://{bucket}/"):
            object_path = filepath.replace(f"supabase://{bucket}/", "")
        elif filepath.startswith("supabase://"):
            object_path = filepath.split("://", 1)[1].split("/", 1)[1]
        elif "/" in filepath or "\\" in filepath:
            # Fallback for paths that were previously local filenames
            basename = os.path.basename(filepath)
            object_path = f"{user_id}/{basename}"

        if object_path:
            try:
                supabase = get_supabase_admin()
                res = supabase.storage.from_(bucket).create_signed_url(object_path, 3600)
                signed_url = res.get("signedURL") or res.get("signedUrl")
                if signed_url:
                    return RedirectResponse(url=signed_url, status_code=307)
            except Exception as e:
                logger.error(f"Error generating signed URL from Supabase Storage: {e}")

        # If file neither exists locally nor in Supabase
        raise FileNotFoundError(f"Media file not found for video {video.get('id')}")

    @staticmethod
    def ensure_local_file(storage_path: Optional[str], user_id: Optional[str] = None) -> str:
        """
        Ensures a media file is available locally on disk (in /tmp/uploads if serverless)
        for processing tasks like FFmpeg audio extraction and chunking.
        Downloads from Supabase Storage if local copy is not present.
        """
        if not storage_path:
            raise FileNotFoundError("Storage path is empty or not specified.")

        # If file already exists on local disk
        if not storage_path.startswith("supabase://") and os.path.exists(storage_path):
            return storage_path

        # If stored in Supabase Storage, download to local temp directory
        bucket = settings.STORAGE_BUCKET_NAME
        if storage_path.startswith(f"supabase://{bucket}/"):
            object_path = storage_path.replace(f"supabase://{bucket}/", "")
        elif storage_path.startswith("supabase://"):
            object_path = storage_path.split("://", 1)[1].split("/", 1)[1]
        else:
            object_path = f"{user_id}/{os.path.basename(storage_path)}" if user_id else os.path.basename(storage_path)

        # Target local file path
        local_dir = ensure_upload_dir(os.path.join(settings.UPLOAD_DIR, user_id or "shared"))
        local_filename = os.path.basename(object_path)
        local_filepath = os.path.join(local_dir, local_filename)

        if os.path.exists(local_filepath) and os.path.getsize(local_filepath) > 0:
            return local_filepath

        supabase = get_supabase_admin()
        data = supabase.storage.from_(bucket).download(object_path)
        with open(local_filepath, "wb") as f:
            f.write(data)

        return local_filepath

    @staticmethod
    def delete_file(storage_path: Optional[str]):
        """
        Deletes media file from local storage and Supabase Storage bucket.
        """
        if not storage_path:
            return

        # Delete local file if it exists
        if not storage_path.startswith("supabase://") and os.path.exists(storage_path):
            try:
                os.remove(storage_path)
            except Exception:
                pass

        # Delete from Supabase Storage
        bucket = settings.STORAGE_BUCKET_NAME
        object_path = None
        if storage_path.startswith(f"supabase://{bucket}/"):
            object_path = storage_path.replace(f"supabase://{bucket}/", "")
        elif storage_path.startswith("supabase://"):
            object_path = storage_path.split("://", 1)[1].split("/", 1)[1]

        if object_path:
            try:
                supabase = get_supabase_admin()
                supabase.storage.from_(bucket).remove([object_path])
            except Exception as e:
                logger.warning(f"Failed to delete object {object_path} from Supabase Storage: {e}")
