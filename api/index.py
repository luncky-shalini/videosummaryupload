import os
import sys

# Ensure backend directory is in sys.path for Vercel Python serverless runtime
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
backend_dir = os.path.join(project_root, "backend")

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Provision FFmpeg static binary if running on serverless
try:
    from services.ffmpeg_resolver import ensure_ffmpeg
    ensure_ffmpeg()
except Exception:
    pass

from main import app

# Vercel ASGI application handler
handler = app
