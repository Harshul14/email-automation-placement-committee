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
"""

import docx

import config

_CACHED_BODY_PARAGRAPHS = None


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


# The two lines in the source template that read as a bullet list
# (they follow "...delighted to schedule a brief virtual meeting to discuss:")
_BULLET_MARKERS = {
    "Batch Profiles and Placement Engagement like Internships and Final Placements",
    "Student interaction opportunities through Guest Lectures, Live Projects and Competitions",
}


def render_html(greeting, company_name):
    """Build the full HTML email body for one recipient."""
    body_paragraphs = _load_static_paragraphs()

    html_parts = [
        '<html><body style="font-family: Calibri, sans-serif; '
        'color:#000099; font-size:11pt; line-height:1.4;">'
    ]
    html_parts.append(f'<p style="margin-top:0; margin-bottom:12pt;">{greeting}</p>')

    bullet_buffer = []

    def flush_bullets():
        if bullet_buffer:
            html_parts.append('<ul style="margin-top:0; margin-bottom:12pt;">')
            for item in bullet_buffer:
                html_parts.append(f"<li>{item}</li>")
            html_parts.append("</ul>")
            bullet_buffer.clear()

    for text in body_paragraphs:
        if not text:
            continue  # skip empty spacer paragraphs from the source docx

        if text in _BULLET_MARKERS:
            bullet_buffer.append(text)
            continue
        else:
            flush_bullets()

        if "Name of company" in text or "‘Name of company’" in text:
            text = text.replace("'Name of company'", company_name)
            text = text.replace("\u2018Name of company\u2019", company_name)
            text = text.replace("..", ".")  # avoid double period when company name already ends in "."

        if "LinkedIn Page" in text:
            text = text.replace(
                "LinkedIn Page",
                f'<a href="{config.LINKEDIN_URL}" style="color:#000099; text-decoration:underline;">LinkedIn Page</a>',
            )
        if "Website" in text:
            text = text.replace(
                "Website",
                f'<a href="{config.WEBSITE_URL}" style="color:#000099; text-decoration:underline;">Website</a>',
            )

        html_parts.append(f'<p style="margin-top:0; margin-bottom:12pt;">{text}</p>')

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
