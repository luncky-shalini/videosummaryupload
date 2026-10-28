import os
import sys

# Ensure current backend directory is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Ensure FFmpeg is available and injected into PATH for Vercel Serverless Function
try:
    from services.ffmpeg_resolver import ensure_ffmpeg
    ensure_ffmpeg()
except Exception:
    pass

from main import app

# Vercel entrypoint handler
handler = app
