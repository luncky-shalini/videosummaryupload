import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

def is_serverless() -> bool:
    """Returns True if executing in a serverless environment (e.g. Vercel, AWS Lambda)."""
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

def get_default_upload_dir() -> str:
    """Uses /tmp on serverless environments where root filesystem is strictly read-only."""
    if is_serverless():
        return "/tmp/uploads"
    return "./uploads"

def get_default_storage_type() -> str:
    """Defaults to Supabase Storage on serverless to guarantee persistent media."""
    if is_serverless():
        return "supabase"
    return "local"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    GROQ_API_KEY: str = ""
    GROQ_CHAT_MODEL: str = "qwen/qwen3.8-27b"
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    MEDIA_STORAGE_TYPE: str = get_default_storage_type() # "local" or "supabase"
    STORAGE_BUCKET_NAME: str = "media-vault"
    UPLOAD_DIR: str = get_default_upload_dir()
    MAX_UPLOAD_SIZE_MB: int = 500

    # YouTube import settings
    YOUTUBE_COOKIES_PATH: Optional[str] = None
    YOUTUBE_COOKIES_CONTENT: Optional[str] = None
    YOUTUBE_PROXY: Optional[str] = None

    @property
    def cors_origins_list(self) -> List[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if self.FRONTEND_URL and self.FRONTEND_URL.strip() not in origins:
            origins.append(self.FRONTEND_URL.strip())
        return origins

settings = Settings()

def ensure_upload_dir(path: str = None) -> str:
    """Safely ensures target upload directory exists without crashing on read-only filesystems."""
    target = path or settings.UPLOAD_DIR
    try:
        os.makedirs(target, exist_ok=True)
        return target
    except OSError:
        # Fallback to /tmp if current directory is read-only
        fallback = "/tmp/uploads"
        try:
            os.makedirs(fallback, exist_ok=True)
        except OSError:
            pass
        return fallback

# Attempt directory creation safely without crashing module import on read-only filesystems
try:
    ensure_upload_dir()
except OSError:
    pass
