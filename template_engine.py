"""
template_engine.py
===================
Renders the source DOCX ('Campus Connect' template) into personalized
HTML email bodies. The template has no signature block and no image
(verified by inspecting the file) — so the signature from config.py is
appended fresh, it is not a "replacement".

Static body text is read ONCE from the DOCX and cached; only the
greeting line and the company-name placeholder are personalized per
recipient, exactly as the source document's structure implies (it does
not attempt to rewrite the rest of the body).

HTML structure matches the actual sent .eml (Outlook rendering) exactly:
  - Paragraphs use line-height:1.284 and margin:0cm 0cm 8pt
  - Yellow highlight is a <span> inside a normal div, not a block bg
  - Bullet list uses disc style with no extra left indent on <li>
  - "To know more" prefix text is bold; link text is <b><u>...</u></b>
  - Company name in the closing line is bold
"""

import docx

import config

_CACHED_BODY_PARAGRAPHS = None

# Shared paragraph style matching actual Outlook rendering
_P_STYLE = (
    'font-family: Calibri, Helvetica, sans-serif; '
    'font-size: 11pt; '
    'color: rgb(0, 0, 153); '
    'line-height: 1.284; '
    'margin: 0cm 0cm 8pt;'
)


def _load_static_paragraphs():
    """Read the DOCX once and return its paragraph texts (nbsp normalized),
    skipping the greeting line (index 0, personalized separately) and the
    trailing blank paragraph."""
    global _CACHED_BODY_PARAGRAPHS
    if _CACHED_BODY_PARAGRAPHS is not None:
        return _CACHED_BODY_PARAGRAPHS

    doc = docx.Document(config.DOCX_TEMPLATE)
    texts = [p.text.replace("\xa0", " ").strip() for p in doc.paragraphs]

    # index 0 is the greeting placeholder -> handled separately per email
    body = texts[1:]
    _CACHED_BODY_PARAGRAPHS = body
    return body


# Lines in the source template that render as bullet points.
# First bullet appears after the AICTE paragraph (single-item list).
# Next two appear after "...brief virtual meeting to discuss:" (two-item list).
_BULLET_MARKERS = {
    "Our MBA program offers a rigorous 102-credit curriculum across diverse specializations including Finance, Marketing, IT & Operations, Analytics, Strategy, and HR.",
    "Batch Profiles and Placement Engagement like Internships and Final Placements",
    "Student interaction opportunities through Guest Lectures, Live Projects and Competitions",
}

# Sentence that gets yellow highlight (as seen in the actual sent .eml)
_YELLOW_HIGHLIGHT_MARKER = "To discuss in detail regarding the Campus Connect Program"


def _apply_bold_phrases(text):
    """Wrap known key phrases in <b> tags to match the actual sent email."""
    bold_phrases = [
        "AICTE-approved institution",
        "102-credit curriculum",
        "Finance, Marketing, IT & Operations, Analytics, Strategy, and HR.",
        "Finance, Marketing, IT & Operations, Analytics, Strategy, and HR",
        "Campus Connect Program",
        "MBA 2025\u201327 and 2026\u201328 cohorts.",
        "MBA 2025\u201327 and 2026\u201328 cohorts",
        "MBA 2025-27 and 2026-28 cohorts.",
        "MBA 2025-27 and 2026-28 cohorts",
        "Internships and Final Placements",
        "Guest Lectures, Live Projects and Competitions",
    ]
    for phrase in bold_phrases:
        if phrase in text:
            text = text.replace(phrase, f"<b>{phrase}</b>")
    return text


def _build_linkedin_website_line(text):
    """Render the 'To know more' line exactly as the actual sent email:
    bold prefix + bold-underline link text."""
    # Split at 'LinkedIn Page' and rebuild
    prefix = "To know more about us, kindly visit our "
    linkedin_label = "LinkedIn Page"
    website_label  = "NMIMS Bengaluru\u2019s Website"
    website_label2 = "NMIMS Bengaluru's Website"
    sep = " or "

    linkedin_html = (
        f'<a href="{config.LINKEDIN_URL}" style="color:rgb(0,0,153);">'
        f'<b><u>{linkedin_label}</u></b></a>'
    )
    website_url_label = website_label if website_label in text else website_label2
    website_html = (
        f'<a href="{config.WEBSITE_URL}" style="color:rgb(0,0,153);">'
        f'<b><u>{website_url_label}</u></b></a>'
        f'<b><u>.</u></b>'
    )

    return (
        f'<div style="{_P_STYLE}">'
        f'<b>{prefix}</b>{linkedin_html}<b>{sep}</b>{website_html}'
        f'</div>'
    )


def render_html(greeting, company_name):
    """Build the full HTML email body for one recipient."""
    body_paragraphs = _load_static_paragraphs()

    html_parts = [
        f'<html><body style="font-family: Calibri, Helvetica, sans-serif; '
        f'font-size: 11pt; color: rgb(0, 0, 153);">'
    ]

    # Greeting line
    html_parts.append(
        f'<div style="{_P_STYLE}">{greeting}</div>'
    )

    bullet_buffer = []

    def flush_bullets():
        if bullet_buffer:
            html_parts.append(
                '<ul style="direction:ltr; text-align:left; '
                'margin-top:0px; margin-bottom:0px; list-style-type:disc;">'
            )
            for item in bullet_buffer:
                item = _apply_bold_phrases(item)
                html_parts.append(
                    f'<li style="font-family:Calibri,Helvetica,sans-serif; '
                    f'font-size:11pt; color:rgb(0,0,153); '
                    f'margin-right:0cm; margin-left:0cm;">'
                    f'<div style="direction:ltr; text-align:left; '
                    f'text-indent:0px; line-height:1.284;">{item}</div>'
                    f'<div style="line-height:1.284; margin:0px 0cm;"><b><br></b></div>'
                    f'</li>'
                )
            html_parts.append('</ul>')
            bullet_buffer.clear()

    for text in body_paragraphs:
        if not text:
            continue  # skip empty spacer paragraphs from the source docx

        if text in _BULLET_MARKERS:
            bullet_buffer.append(text)
            continue
        else:
            flush_bullets()

        # Company name placeholder substitution
        if "Name of company" in text or "\u2018Name of company\u2019" in text:
            text = text.replace("'Name of company'", company_name)
            text = text.replace("\u2018Name of company\u2019", company_name)
            text = text.replace("..", ".")

        # LinkedIn / Website line — rendered specially to match the .eml exactly
        if "kindly visit our" in text or "To know more" in text:
            html_parts.append(_build_linkedin_website_line(text))
            continue

        # Yellow highlight sentence — use <span> inside a normal div (not block bg)
        if _YELLOW_HIGHLIGHT_MARKER in text:
            html_parts.append(
                f'<div style="{_P_STYLE}">'
                f'<span style="background-color:rgb(255,255,0);">'
                f'<b>{text}</b>'
                f'</span>'
                f'</div>'
            )
            continue

        # Closing "We look forward" line — bold the company name
        if "We look forward" in text and company_name in text:
            idx = text.find(company_name)
            before = text[:idx]
            after  = text[idx + len(company_name):]
            html_parts.append(
                f'<div style="{_P_STYLE}">'
                f'{before}<b>{company_name}</b>{after}'
                f'</div>'
            )
            continue

        # General paragraph — apply bold phrases
        text = _apply_bold_phrases(text)
        html_parts.append(f'<div style="{_P_STYLE}">{text}</div>')

    flush_bullets()

    html_parts.append(config.SIGNATURE_HTML)
    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def render_plaintext_fallback(greeting, company_name):
    return (
        f"{greeting}\n\n"
        f"Greetings from NMIMS Bengaluru! We are reaching out regarding the "
        f"Campus Connect Program and would welcome the opportunity to partner "
        f"with {company_name}.\n\n"
        f"Best Regards,\nHarshul Varshney\nMember | Placement Committee\n"
        f"SVKM's Narsee Monjee Institute of Management Studies\n"
    )
