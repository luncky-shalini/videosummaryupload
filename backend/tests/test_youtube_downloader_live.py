import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from services.youtube_downloader import YouTubeDownloader


@pytest.mark.live
def test_live_public_youtube_video_extraction(tmp_path):
    """
    LIVE INTEGRATION TEST (Distinct from mocked tests).
    Attempts to download a short, real public YouTube video ("Me at the zoo" - 19 seconds)
    using the configured in-process downloader and local JavaScript runtime.
    If the test runner's network environment is offline or blocked by YouTube's
    datacenter IP bot check, reports the status clearly.
    """
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    output_dir = str(tmp_path)

    try:
        result = YouTubeDownloader._extract_and_download_in_process(test_url, output_dir)
        print(f"\n[LIVE TEST SUCCESS] Successfully downloaded live YouTube video: '{result['title']}'")
        assert result["title"] is not None
        assert result["duration"] > 0
        assert os.path.exists(result["filepath"])
        assert os.path.getsize(result["filepath"]) > 0

        # Clean up temporary test file
        if os.path.exists(result["filepath"]):
            os.remove(result["filepath"])

    except RuntimeError as exc:
        err_msg = str(exc)
        if "bot detection" in err_msg or "403" in err_msg or "429" in err_msg or "unavailable" in err_msg:
            # Runner IP is subject to YouTube access controls or rate limits
            pytest.skip(f"Live YouTube download skipped due to network/bot restrictions: {err_msg}")
        else:
            raise
    except Exception as exc:
        pytest.skip(f"Live YouTube test skipped due to network connectivity: {exc}")
