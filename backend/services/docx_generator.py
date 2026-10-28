import io
import re
from typing import Dict, Any, List
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Disallowed XML 1.0 control characters
XML_ILLEGAL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]')

def _clean_xml_str(text: Any) -> str:
    """Strips invalid XML 1.0 control characters that can cause python-docx to crash."""
    if text is None:
        return ""
    return XML_ILLEGAL_CHARS_RE.sub('', str(text))

class DocxReportGenerator:
    @staticmethod
    def generate_docx(
        video_title: str,
        video_metadata: Dict[str, Any],
        summary: Dict[str, Any],
        segments: List[Dict[str, Any]],
        export_type: str = "full"
    ) -> bytes:
        """
        Builds a Microsoft Word (.docx) document with structured formatting,
        callouts, tables, and full transcript.
        Supports export_type='full', 'synopsis', or 'transcript'.
        """
        doc = Document()

        # Document Header
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(_clean_xml_str(video_title or "Video Analysis"))
        title_run.bold = True
        title_run.font.size = Pt(20)
        title_run.font.color.rgb = RGBColor(15, 23, 42)

        dur_mins = int(video_metadata.get('duration', 0) // 60)
        dur_secs = int(video_metadata.get('duration', 0) % 60)
        meta_para = doc.add_paragraph()
        meta_text = (
            f"Generated: {_clean_xml_str(video_metadata.get('date', 'Today'))}  |  "
            f"Duration: {dur_mins}m {dur_secs}s  |  "
            f"Type: {'Meeting Recording' if summary.get('is_meeting') else 'General Video'}"
        )
        meta_run = meta_para.add_run(meta_text)
        meta_run.font.size = Pt(9.5)
        meta_run.font.color.rgb = RGBColor(100, 116, 139)

        doc.add_paragraph().paragraph_format.space_after = Pt(10)

        # Synopsis Sections (Executive Summary, Decisions, Action Items, Topics, Moments)
        if export_type in ("full", "synopsis") and summary:
            # Executive Summary
            h1 = doc.add_heading("Executive Summary", level=1)
            h1.paragraph_format.space_before = Pt(12)
            exec_text = summary.get("executive_summary", "")
            for p in exec_text.split("\n\n"):
                if p.strip():
                    p_run = doc.add_paragraph(_clean_xml_str(p.strip()))
                    p_run.paragraph_format.space_after = Pt(6)

            # Meeting Decisions & Action Items
            if summary.get("is_meeting"):
                doc.add_heading("Meeting Insights & Decisions", level=1)
                if summary.get("meeting_overview"):
                    doc.add_paragraph(_clean_xml_str(f"Overview: {summary['meeting_overview']}"))

                decisions = summary.get("decisions", [])
                if decisions:
                    doc.add_heading("Key Decisions", level=2)
                    for d in decisions:
                        doc.add_paragraph(_clean_xml_str(d), style='List Bullet')

                action_items = summary.get("action_items", [])
                if action_items:
                    doc.add_heading("Action Items", level=2)
                    table = doc.add_table(rows=1, cols=3)
                    table.style = 'Table Grid'
                    hdr_cells = table.rows[0].cells
                    hdr_cells[0].text = 'Task / Action Item'
                    hdr_cells[1].text = 'Owner'
                    hdr_cells[2].text = 'Deadline'
                    
                    for item in action_items:
                        row_cells = table.add_row().cells
                        if isinstance(item, dict):
                            row_cells[0].text = _clean_xml_str(item.get("item", ""))
                            row_cells[1].text = _clean_xml_str(item.get("owner", "Unassigned"))
                            row_cells[2].text = _clean_xml_str(item.get("deadline", "Not specified"))
                        else:
                            row_cells[0].text = _clean_xml_str(str(item))
                            row_cells[1].text = "Unassigned"
                            row_cells[2].text = "Not specified"

            # Key Topics
            key_topics = summary.get("key_topics", [])
            if key_topics:
                doc.add_heading("Key Topics", level=1)
                for t in key_topics:
                    doc.add_paragraph(_clean_xml_str(t), style='List Bullet')

            # Key Moments
            key_moments = summary.get("key_moments", [])
            if key_moments:
                doc.add_heading("Key Moments & Timeline", level=1)
                for km in key_moments:
                    p = doc.add_paragraph()
                    if isinstance(km, dict):
                        r_time = p.add_run(_clean_xml_str(f"[{km.get('time', '00:00')}] {km.get('title', '')}: "))
                        r_time.bold = True
                        p.add_run(_clean_xml_str(km.get("description", "")))
                    else:
                        p.add_run(_clean_xml_str(str(km)))

        # Chronological Dialogue Transcript
        if export_type in ("full", "transcript") and segments:
            if export_type == "full":
                doc.add_page_break()
            doc.add_heading("Chronological Dialogue Transcript", level=1)
            for seg in segments:
                mins = int(seg.get("start_time", 0) // 60)
                secs = int(seg.get("start_time", 0) % 60)
                speaker = seg.get("display_name") or seg.get("speaker_label", "Speaker")
                
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                r_spk = p.add_run(_clean_xml_str(f"[{mins:02d}:{secs:02d}] {speaker}: "))
                r_spk.bold = True
                r_spk.font.color.rgb = RGBColor(37, 99, 235)
                p.add_run(_clean_xml_str(seg.get("text", "")))

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

