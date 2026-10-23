import io
import html
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from services.pdf_font_manager import get_unicode_pdf_fonts

def _clean_text(val: Any) -> str:
    """Escapes XML entities while preserving valid Unicode glyphs for ReportLab Paragraphs."""
    if val is None:
        return ""
    text = str(val).strip()
    return html.escape(text)

class PDFReportGenerator:
    @staticmethod
    def generate_pdf(
        video_title: str,
        video_metadata: Dict[str, Any],
        summary: Dict[str, Any],
        segments: List[Dict[str, Any]],
        export_type: str = "full"
    ) -> bytes:
        """
        Generates a publication-grade Unicode-safe PDF report using ReportLab.
        Supports:
        - export_type='synopsis': Executive summary, decisions, topics, moments
        - export_type='transcript': Full timestamped dialogue transcript with speakers
        - export_type='full': Complete combined report
        Preserves non-English scripts (Chinese, Telugu, Hindi, Spanish, Bengali, etc.)
        """
        reg_font, bold_font = get_unicode_pdf_fonts()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        # Typography bound to verified Unicode font family
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Normal'],
            fontName=bold_font,
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=8
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName=reg_font,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=14
        )
        h1_style = ParagraphStyle(
            'H1',
            parent=styles['Normal'],
            fontName=bold_font,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor('#1e293b'),
            spaceBefore=12,
            spaceAfter=6
        )
        h2_style = ParagraphStyle(
            'H2',
            parent=styles['Normal'],
            fontName=bold_font,
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor('#334155'),
            spaceBefore=8,
            spaceAfter=4
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName=reg_font,
            fontSize=9,
            leading=13.5,
            textColor=colors.HexColor('#334155'),
            spaceAfter=5
        )
        bullet_style = ParagraphStyle(
            'Bullet',
            parent=body_style,
            leftIndent=15,
            firstLineIndent=-10,
            spaceAfter=3
        )
        transcript_speaker = ParagraphStyle(
            'SpeakerLabel',
            parent=styles['Normal'],
            fontName=bold_font,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#2563eb')
        )
        transcript_text = ParagraphStyle(
            'TranscriptBody',
            parent=styles['Normal'],
            fontName=reg_font,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor('#1e293b')
        )

        elements = []

        # Document Header
        report_subtitle = (
            "Executive Synopsis Report" if export_type == "synopsis"
            else "Dialogue Transcript Report" if export_type == "transcript"
            else "AI Video Synopsis & Meeting Intelligence Report"
        )
        elements.append(Paragraph(_clean_text(report_subtitle), subtitle_style))
        elements.append(Paragraph(_clean_text(video_title), title_style))

        dur_str = f"{int(video_metadata.get('duration', 0) // 60)} min {int(video_metadata.get('duration', 0) % 60)} sec"
        meta_info = (
            f"<b>Generated:</b> {_clean_text(video_metadata.get('date', 'Today'))} &nbsp;|&nbsp; "
            f"<b>Duration:</b> {dur_str} &nbsp;|&nbsp; "
            f"<b>Type:</b> {'Meeting Recording' if summary.get('is_meeting') else 'General Video'}"
        )
        elements.append(Paragraph(meta_info, subtitle_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=14))

        include_synopsis = export_type in ("full", "synopsis")
        include_transcript = export_type in ("full", "transcript")

        # 1. Synopsis Section
        if include_synopsis and summary:
            # Executive Summary
            elements.append(Paragraph("Executive Summary", h1_style))
            exec_text = summary.get("executive_summary") or "No executive summary available."
            for p in exec_text.split("\n\n"):
                if p.strip():
                    elements.append(Paragraph(_clean_text(p), body_style))
            elements.append(Spacer(1, 8))

            # Detailed Synopsis
            if summary.get("detailed_synopsis"):
                elements.append(Paragraph("Detailed Synopsis", h1_style))
                for p in summary["detailed_synopsis"].split("\n\n"):
                    if p.strip():
                        elements.append(Paragraph(_clean_text(p), body_style))
                elements.append(Spacer(1, 8))

            # Meeting Decisions & Action Items
            if summary.get("is_meeting"):
                elements.append(Paragraph("Meeting Insights & Decisions", h1_style))
                if summary.get("meeting_overview"):
                    elements.append(Paragraph(f"<b>Overview:</b> {_clean_text(summary['meeting_overview'])}", body_style))

                decisions = summary.get("decisions", [])
                if decisions:
                    elements.append(Paragraph("Decisions Agreed:", h2_style))
                    for d in decisions:
                        elements.append(Paragraph(f"&bull; {_clean_text(d)}", bullet_style))

                action_items = summary.get("action_items", [])
                if action_items:
                    elements.append(Spacer(1, 4))
                    elements.append(Paragraph("Action Items & Deliverables:", h2_style))
                    table_data = [[
                        Paragraph("<b>Task / Deliverable</b>", body_style),
                        Paragraph("<b>Owner</b>", body_style),
                        Paragraph("<b>Deadline</b>", body_style)
                    ]]
                    for item in action_items:
                        table_data.append([
                            Paragraph(_clean_text(item.get("item", "")), body_style),
                            Paragraph(_clean_text(item.get("owner", "Unassigned")), body_style),
                            Paragraph(_clean_text(item.get("deadline", "Not specified")), body_style)
                        ])

                    t = Table(table_data, colWidths=[270, 125, 125])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0f172a')),
                        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                        ('VALIGN', (0,0), (-1,-1), 'TOP'),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                        ('TOPPADDING', (0,0), (-1,-1), 4),
                    ]))
                    elements.append(t)
                    elements.append(Spacer(1, 8))

            # Key Topics
            key_topics = summary.get("key_topics", [])
            if key_topics:
                elements.append(Paragraph("Key Topics Covered", h1_style))
                for topic in key_topics:
                    elements.append(Paragraph(f"&bull; {_clean_text(topic)}", bullet_style))
                elements.append(Spacer(1, 6))

            # Conclusions
            conclusions = summary.get("conclusions", [])
            if conclusions:
                elements.append(Paragraph("Outcomes & Conclusions", h1_style))
                for conc in conclusions:
                    elements.append(Paragraph(f"&bull; {_clean_text(conc)}", bullet_style))
                elements.append(Spacer(1, 6))

            # Key Moments with Timestamps
            key_moments = summary.get("key_moments", [])
            if key_moments:
                elements.append(Paragraph("Key Moments & Timeline", h1_style))
                for km in key_moments:
                    km_time = _clean_text(km.get('time', '00:00'))
                    km_title = _clean_text(km.get('title', ''))
                    km_desc = _clean_text(km.get('description', ''))
                    km_text = f"<b>[{km_time}] {km_title}</b>: {km_desc}"
                    elements.append(Paragraph(km_text, body_style))
                elements.append(Spacer(1, 8))

        # 2. Transcript Section
        if include_transcript and segments:
            if include_synopsis:
                elements.append(PageBreak())

            elements.append(Paragraph("Chronological Dialogue Transcript", h1_style))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=8))

            for seg in segments:
                mins = int(seg.get("start_time", 0) // 60)
                secs = int(seg.get("start_time", 0) % 60)
                speaker = seg.get("display_name") or seg.get("speaker_label", "Speaker")
                line_speaker = f"[{mins:02d}:{secs:02d}] {_clean_text(speaker)}"
                elements.append(Paragraph(line_speaker, transcript_speaker))
                elements.append(Paragraph(_clean_text(seg.get("text", "")), transcript_text))
                elements.append(Spacer(1, 3))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
