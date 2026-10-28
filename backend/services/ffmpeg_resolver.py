import os
import sys
import shutil
import logging
import subprocess
import tempfile
import re
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

_RESOLVED_FFMPEG_PATH: Optional[str] = None
_RESOLVED_FFPROBE_PATH: Optional[str] = None
_RESOLVED_BIN_DIR: Optional[str] = None


def get_target_bin_dir() -> str:
    """
    Returns a writable directory for binary shims and executables.
    On serverless (Vercel / AWS Lambda), strictly uses /tmp/bin.
    On local/Windows, uses the system temp directory's bin subdirectory.
    """
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        target = "/tmp/bin"
    else:
        target = os.path.join(tempfile.gettempdir(), "ffmpeg_bin")

    try:
        os.makedirs(target, exist_ok=True)
    except OSError:
        target = "/tmp/bin"
        try:
            os.makedirs(target, exist_ok=True)
        except OSError:
            pass
    return target


def _add_to_path(directory: str):
    """Prepends directory to PATH environment variable if not already present."""
    if not directory:
        return
    current_path = os.environ.get("PATH", "")
    paths = current_path.split(os.pathsep)
    norm_target = os.path.normpath(directory)
    if not any(os.path.normpath(p) == norm_target for p in paths if p):
        os.environ["PATH"] = directory + os.pathsep + current_path
        logger.debug(f"Prepended {directory} to os.environ['PATH']")


def _verify_executable(path: str) -> bool:
    """Verifies that the given path is an executable binary and returns version output."""
    if not path or not os.path.exists(path):
        return False
    try:
        res = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=5)
        return res.returncode == 0
    except Exception:
        return False


def _create_ffprobe_shim(bin_dir: str, ffmpeg_exe: str) -> Optional[str]:
    """
    Creates a cross-platform ffprobe compatibility shim script that executes ffmpeg
    and outputs ffprobe-compatible JSON for duration, streams, and format.
    Ensures that any tool expecting 'ffprobe' on PATH succeeds.
    """
    shim_py = os.path.join(bin_dir, "_ffprobe_runner.py")
    script_content = f'''#!/usr/bin/env python3
import sys
import os
import re
import json
import subprocess

FFMPEG_EXE = {repr(ffmpeg_exe)}

def main():
    args = sys.argv[1:]
    target_file = None
    for a in reversed(args):
        if not a.startswith("-") and os.path.exists(a):
            target_file = a
            break

    if not target_file:
        for a in reversed(args):
            if not a.startswith("-"):
                target_file = a
                break

    if not target_file or not os.path.exists(target_file):
        print(json.dumps({{"error": "No valid media file provided", "format": {{}}, "streams": []}}))
        sys.exit(0)

    try:
        res = subprocess.run([FFMPEG_EXE, "-i", target_file], capture_output=True, text=True)
        stderr = res.stderr or ""
    except Exception as e:
        print(json.dumps({{"error": str(e), "format": {{}}, "streams": []}}))
        sys.exit(0)

    duration = 0.0
    dur_m = re.search(r"Duration:\\s*(\\d+):(\\d+):(\\d+(?:\\.\\d+)?)", stderr)
    if dur_m:
        h, m, s = dur_m.groups()
        duration = int(h) * 3600 + int(m) * 60 + float(s)

    file_size = os.path.getsize(target_file) if os.path.exists(target_file) else 0

    streams = []
    # Video streams
    for vm in re.finditer(r"Stream\\s+#\\d+:\\d+.*?Video:\\s*([^,\\n]+).*?,\\s*(\\d+)x(\\d+)", stderr):
        codec = vm.group(1).strip()
        width = int(vm.group(2))
        height = int(vm.group(3))
        streams.append({{"codec_type": "video", "codec_name": codec, "width": width, "height": height}})

    # Audio streams
    for am in re.finditer(r"Stream\\s+#\\d+:\\d+.*?Audio:\\s*([^,\\n]+)", stderr):
        codec = am.group(1).strip()
        streams.append({{"codec_type": "audio", "codec_name": codec}})

    out = {{
        "format": {{
            "filename": target_file,
            "duration": str(duration),
            "size": str(file_size)
        }},
        "streams": streams
    }}
    print(json.dumps(out))

if __name__ == "__main__":
    main()
'''
    try:
        with open(shim_py, "w", encoding="utf-8") as f:
            f.write(script_content)
        os.chmod(shim_py, 0o755)

        # On POSIX: create executable `ffprobe` shim
        shim_sh = os.path.join(bin_dir, "ffprobe")
        with open(shim_sh, "w", encoding="utf-8") as f:
            f.write(f'#!/bin/sh\nexec python3 "{shim_py}" "$@"\n')
        os.chmod(shim_sh, 0o755)

        # On Windows: create `ffprobe.cmd` shim
        shim_cmd = os.path.join(bin_dir, "ffprobe.cmd")
        with open(shim_cmd, "w", encoding="utf-8") as f:
            f.write(f'@echo off\npython "{shim_py}" %*\n')

        return shim_sh if sys.platform != "win32" else shim_cmd
    except Exception as e:
        logger.debug(f"Could not write ffprobe shim: {e}")
        return None


def ensure_ffmpeg() -> str:
    """
    Finds or provisions an executable FFmpeg binary and configures PATH so that
    FFmpeg is available globally for subprocess calls, yt-dlp, and media services.
    Returns the absolute path to the FFmpeg executable.
    """
    global _RESOLVED_FFMPEG_PATH, _RESOLVED_FFPROBE_PATH, _RESOLVED_BIN_DIR

    if _RESOLVED_FFMPEG_PATH and os.path.exists(_RESOLVED_FFMPEG_PATH):
        return _RESOLVED_FFMPEG_PATH

    bin_dir = get_target_bin_dir()
    try:
        os.makedirs(bin_dir, exist_ok=True)
    except OSError:
        pass
    _RESOLVED_BIN_DIR = bin_dir

    # 1. Check if standard system ffmpeg is already on PATH and working
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg and _verify_executable(system_ffmpeg):
        _RESOLVED_FFMPEG_PATH = os.path.abspath(system_ffmpeg)
        _RESOLVED_FFPROBE_PATH = shutil.which("ffprobe")
        logger.info(f"Using system FFmpeg at: {_RESOLVED_FFMPEG_PATH}")
        return _RESOLVED_FFMPEG_PATH

    # 2. Check if imageio-ffmpeg is installed (bundles static binary)
    source_ffmpeg = None
    try:
        import imageio_ffmpeg
        candidate = imageio_ffmpeg.get_ffmpeg_exe()
        if candidate and os.path.exists(candidate):
            source_ffmpeg = candidate
            logger.info(f"Detected imageio-ffmpeg bundled binary at: {source_ffmpeg}")
    except ImportError:
        logger.debug("imageio-ffmpeg is not installed.")
    except Exception as e:
        logger.debug(f"imageio-ffmpeg error: {e}")

    # 3. Provision executable in target bin directory
    target_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    target_ffmpeg = os.path.join(bin_dir, target_name)

    if source_ffmpeg and os.path.exists(source_ffmpeg):
        try:
            # Copy or symlink to target bin dir
            if not os.path.exists(target_ffmpeg) or os.path.getsize(target_ffmpeg) != os.path.getsize(source_ffmpeg):
                try:
                    # Attempt symlink first for speed/space
                    if sys.platform != "win32":
                        if os.path.islink(target_ffmpeg) or os.path.exists(target_ffmpeg):
                            os.remove(target_ffmpeg)
                        os.symlink(source_ffmpeg, target_ffmpeg)
                    else:
                        shutil.copy2(source_ffmpeg, target_ffmpeg)
                except (OSError, AttributeError):
                    shutil.copy2(source_ffmpeg, target_ffmpeg)

            # Ensure execution permissions (0o755 = rwxr-xr-x)
            try:
                os.chmod(target_ffmpeg, 0o755)
            except OSError:
                pass

            if _verify_executable(target_ffmpeg):
                _RESOLVED_FFMPEG_PATH = target_ffmpeg
            elif _verify_executable(source_ffmpeg):
                _RESOLVED_FFMPEG_PATH = source_ffmpeg
        except Exception as e:
            logger.warning(f"Error staging ffmpeg in {bin_dir}: {e}")
            if _verify_executable(source_ffmpeg):
                _RESOLVED_FFMPEG_PATH = source_ffmpeg

    # 4. Fallback check inside bin directory
    if not _RESOLVED_FFMPEG_PATH and os.path.exists(target_ffmpeg) and _verify_executable(target_ffmpeg):
        _RESOLVED_FFMPEG_PATH = target_ffmpeg

    # 5. Inject bin directory into PATH so child processes & yt-dlp find it
    if _RESOLVED_FFMPEG_PATH:
        ffmpeg_parent_dir = os.path.dirname(_RESOLVED_FFMPEG_PATH)
        _add_to_path(ffmpeg_parent_dir)
        _add_to_path(bin_dir)

        # Set up ffprobe shim if native ffprobe is missing
        native_ffprobe = shutil.which("ffprobe")
        if native_ffprobe and _verify_executable(native_ffprobe):
            _RESOLVED_FFPROBE_PATH = native_ffprobe
        else:
            shim_path = _create_ffprobe_shim(bin_dir, _RESOLVED_FFMPEG_PATH)
            _RESOLVED_FFPROBE_PATH = shim_path

        return _RESOLVED_FFMPEG_PATH

    raise FileNotFoundError(
        "FFmpeg binary could not be found or provisioned. "
        "Please ensure 'imageio-ffmpeg' is installed in requirements.txt or FFmpeg is installed on system PATH."
    )


def get_ffmpeg_path() -> str:
    """Returns the resolved FFmpeg executable path, initializing if needed."""
    return ensure_ffmpeg()


def get_ffprobe_path() -> Optional[str]:
    """Returns the resolved FFprobe executable path or shim, or None if unavailable."""
    try:
        ensure_ffmpeg()
        return _RESOLVED_FFPROBE_PATH
    except Exception:
        return None


def get_ffmpeg_dir() -> str:
    """
    Returns the directory containing the resolved FFmpeg binary.
    Ideal for configuring yt-dlp 'ffmpeg_location'.
    """
    ffmpeg_exe = ensure_ffmpeg()
    return os.path.dirname(ffmpeg_exe)


def parse_media_metadata_with_ffmpeg(file_path: str, ffmpeg_bin: Optional[str] = None) -> Dict[str, Any]:
    """
    Extracts media metadata (duration, resolution, has_video, has_audio) directly
    using FFmpeg inspect (-i) stderr output.
    Guarantees robust metadata extraction even when ffprobe is completely absent.
    """
    bin_path = ffmpeg_bin or get_ffmpeg_path()
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    try:
        res = subprocess.run([bin_path, "-i", file_path], capture_output=True, text=True, timeout=15)
        stderr = res.stderr or ""
    except Exception as e:
        return {
            "duration": 0.0,
            "size_bytes": file_size,
            "has_video": True,
            "has_audio": True,
            "error": str(e)
        }

    # Extract duration: Duration: HH:MM:SS.ss
    duration = 0.0
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if dur_match:
        h, m, s = dur_match.groups()
        duration = round(int(h) * 3600 + int(m) * 60 + float(s), 2)

    # Detect video stream and dimensions
    has_video = False
    width = None
    height = None
    video_match = re.search(r"Stream\s+#\d+:\d+.*?Video:\s*([^,\n]+).*?,\s*(\d+)x(\d+)", stderr)
    if video_match:
        has_video = True
        width = int(video_match.group(2))
        height = int(video_match.group(3))
    elif "Video:" in stderr:
        has_video = True

    # Detect audio stream
    has_audio = "Audio:" in stderr

    return {
        "duration": duration,
        "size_bytes": file_size,
        "has_video": has_video,
        "has_audio": has_audio,
        "width": width,
        "height": height
    }
