import os
import logging
from typing import Tuple
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

_REGISTERED_FONTS = {}

def get_unicode_pdf_fonts() -> Tuple[str, str]:
    """
    Finds, registers, and returns (regular_font_name, bold_font_name)
    supporting global multilingual scripts (Telugu, Hindi, Chinese, Spanish, Bengali, English).
    """
    global _REGISTERED_FONTS
    if "regular" in _REGISTERED_FONTS and "bold" in _REGISTERED_FONTS:
        return _REGISTERED_FONTS["regular"], _REGISTERED_FONTS["bold"]

    # Candidate font configurations in order of multilingual completeness
    candidates = [
        # Windows: Arial Unicode MS (Covers virtually all Unicode glyphs: CJK, Indic, Latin, Arabic)
        ("ArialUnicode", "C:/Windows/Fonts/ARIALUNI.TTF", "ArialUnicode", "C:/Windows/Fonts/ARIALUNI.TTF"),
        # Windows: Nirmala UI (Superb coverage for Telugu, Devanagari/Hindi, Bengali, Latin)
        ("NirmalaUI", "C:/Windows/Fonts/Nirmala.ttf", "NirmalaUI-Bold", "C:/Windows/Fonts/NirmalaB.ttf"),
        # Windows: Segoe UI
        ("SegoeUI", "C:/Windows/Fonts/segoeui.ttf", "SegoeUI-Bold", "C:/Windows/Fonts/segoeuib.ttf"),
        # Windows: Arial standard
        ("ArialStandard", "C:/Windows/Fonts/arial.ttf", "ArialStandard-Bold", "C:/Windows/Fonts/arialbd.ttf"),
        # Linux / Vercel paths
        ("NotoSans", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "NotoSans-Bold", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]

    for reg_name, reg_path, bold_name, bold_path in candidates:
        if os.path.exists(reg_path):
            try:
                pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                    actual_bold = bold_name
                else:
                    actual_bold = reg_name

                _REGISTERED_FONTS["regular"] = reg_name
                _REGISTERED_FONTS["bold"] = actual_bold
                logger.info(f"Registered Unicode PDF fonts: {reg_name}, {actual_bold} from {reg_path}")
                return reg_name, actual_bold
            except Exception as e:
                logger.warning(f"Failed to register font {reg_path}: {e}")

    # Fallback default
    _REGISTERED_FONTS["regular"] = "Helvetica"
    _REGISTERED_FONTS["bold"] = "Helvetica-Bold"
    return "Helvetica", "Helvetica-Bold"
