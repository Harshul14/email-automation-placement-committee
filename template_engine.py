"""
template_engine.py
===================
Renders the 'Invitation for Campus Hiring' template into personalized
HTML email bodies, matching the actual sent .eml from NMIMS, Bengaluru.

Template body (greeting → before regards) is sourced directly from the
decoded plain-text of the reference .eml, which is the authoritative
source for this template.

HTML structure matches the actual sent .eml (Outlook rendering) exactly:
  - Paragraphs use line-height:1.284 and margin:0cm 0cm 8pt
  - Bullet list uses disc style; each bullet item is bold
  - Corporate Presentation and Placement Brochure are bold+underline links
  - Company name in the closing "We look forward" line is bold
  - "Kindly let us know" closing line appears before the signature
"""

import config

# ---------------------------------------------------------------------------
# Shared paragraph style matching actual Outlook rendering
# ---------------------------------------------------------------------------
_P_STYLE = (
    'font-family: Calibri, Helvetica, sans-serif; '
    'font-size: 11pt; '
    'color: rgb(0, 0, 153); '
    'line-height: 1.284; '
    'margin: 0cm 0cm 8pt;'
)

# ---------------------------------------------------------------------------
# Static body paragraphs (in order), excluding the personalized greeting
# and the closing "We look forward" line (handled separately).
# ---------------------------------------------------------------------------

# Bullet items for the Job Description list
_JD_BULLETS = [
    "Job Role",
    "Job Location",
    "Criteria",
    "Specialization",
    "Stipend/ CTC details (with both fixed and variable component)",
]

# Bold phrases to wrap in <b> tags (applied to non-link, non-bullet paragraphs)
_BOLD_PHRASES = [
    "AICTE-approved institution",
    "102-credit curriculum",
    "Finance, Marketing, IT & Operations, Analytics, Strategy, and HR.",
    "Finance, Marketing, IT & Operations, Analytics, Strategy, and HR",
    "Summer Internship and Final Placement Season",
    "Job Description",
]


def _apply_bold_phrases(text: str) -> str:
    """Wrap known key phrases in <b> tags to match the actual sent email."""
    for phrase in _BOLD_PHRASES:
        if phrase in text:
            text = text.replace(phrase, f"<b>{phrase}</b>")
    return text


def _build_bullet_list() -> str:
    """Render the Job Description bullet list exactly as in the .eml."""
    items_html = ""
    for item in _JD_BULLETS:
        items_html += (
            f'<li style="font-family:Calibri,Helvetica,sans-serif; '
            f'font-size:11pt; color:rgb(0,0,153); '
            f'direction:ltr; align-self:start; '
            f'margin-right:0cm; margin-left:0cm;">'
            f'<div style="direction:ltr; text-align:left; '
            f'text-indent:0px; line-height:1.284; margin:0cm 0px 8pt;">'
            f'<b>{item}</b>'
            f'</div>'
            f'</li>'
        )
    return (
        '<ul style="direction:ltr; text-align:left; '
        'margin-top:0px; margin-bottom:0px; list-style-type:disc; '
        'background-color:rgb(255,255,255); flex-direction:column; display:flex;">'
        + items_html +
        '</ul>'
    )


def _build_brochure_line() -> str:
    """Render the Corporate Presentation / Placement Brochure link line,
    matching the bold+underline link style from the actual .eml."""
    corp_href = config.CORPORATE_PRESENTATION_URL
    brochure_href = config.PLACEMENT_BROCHURE_URL

    corp_link = (
        f'<a href="{corp_href}" style="color:rgb(0,0,153);">'
        f'<b><u>Corporate Presentation</u></b></a>'
    )
    brochure_link = (
        f'<a href="{brochure_href}" style="color:rgb(0,0,153);">'
        f'<b>Placement Brochure</b></a>'
    )

    return (
        f'<div style="{_P_STYLE}">'
        f'Also, please find the link&nbsp;to&nbsp;our {corp_link}'
        f'&nbsp;and {brochure_link} for your kind perusal.'
        f'</div>'
    )


def render_html(greeting: str, company_name: str) -> str:
    """Build the full HTML email body for one recipient.

    Args:
        greeting:     The personalised salutation, e.g. "Dear Mr./Ms. Shah,"
        company_name: The company name used in the closing line.

    Returns:
        A complete HTML string ready to embed as the email body.
    """
    parts = [
        '<html><body style="font-family: Calibri, Helvetica, sans-serif; '
        'font-size: 11pt; color: rgb(0, 0, 153);">'
    ]

    def p(text: str) -> str:
        """Wrap text in a standard paragraph div."""
        return f'<div style="{_P_STYLE}">{text}</div>'

    # ------------------------------------------------------------------
    # 1. Salutation (personalised)
    # ------------------------------------------------------------------
    parts.append(p(greeting))

    # ------------------------------------------------------------------
    # 2. Opening lines
    # ------------------------------------------------------------------
    parts.append(p("Greetings of the day from&nbsp;NMIMS, Bengaluru!"))
    parts.append(p("Hope you are safe and doing well."))

    # ------------------------------------------------------------------
    # 3. Institution / programme paragraph
    # ------------------------------------------------------------------
    inst_para = (
        "As an <b>AICTE-approved institution</b>, NMIMS Bengaluru has established itself as a hub of academic "
        "excellence and innovation within the dynamic landscape of Bengaluru. Our MBA program offers a rigorous "
        "<b>102-credit curriculum</b> across diverse specializations including "
        "<b>Finance, Marketing, IT &amp; Operations, Analytics, Strategy, and HR.</b>"
    )
    parts.append(p(inst_para))

    # ------------------------------------------------------------------
    # 4. Placement season invitation
    # ------------------------------------------------------------------
    season_para = (
        "As we prepare&nbsp;for&nbsp;the&nbsp;forthcoming "
        "<b>Summer Internship and Final Placement Season</b>, we are pleased&nbsp;to&nbsp;invite "
        "your esteemed organization&nbsp;to&nbsp;engage with our student cohort.&nbsp;"
    )
    parts.append(p(season_para))

    # ------------------------------------------------------------------
    # 5. Role-specific details request
    # ------------------------------------------------------------------
    details_para = (
        "To&nbsp;initiate the process, we kindly request you&nbsp;to&nbsp;share the role-specific details, "
        "which will help us drive student interest and ensure a stronger fit between your requirements "
        "and our students\u2019 capabilities."
    )
    parts.append(p(details_para))

    # ------------------------------------------------------------------
    # 6. Job Description intro
    # ------------------------------------------------------------------
    jd_intro = (
        "We would require the <b>Job Description</b>&nbsp;comprising of the following details:"
    )
    parts.append(p(jd_intro))

    # ------------------------------------------------------------------
    # 7. Bullet list
    # ------------------------------------------------------------------
    parts.append(_build_bullet_list())

    # ------------------------------------------------------------------
    # 8. Corporate Presentation / Placement Brochure links
    # ------------------------------------------------------------------
    parts.append(_build_brochure_line())

    # ------------------------------------------------------------------
    # 9. "We look forward" closing line — company name is bold
    # ------------------------------------------------------------------
    forward_para = (
        f"We look&nbsp;forward&nbsp;to&nbsp;partnering with "
        f"<b>{company_name}</b> and welcoming your organization during our Placement Season."
    )
    parts.append(p(forward_para))

    # ------------------------------------------------------------------
    # 10. Concerns line
    # ------------------------------------------------------------------
    parts.append(p("Kindly let us know in case of any concerns."))

    # ------------------------------------------------------------------
    # 11. Signature
    # ------------------------------------------------------------------
    parts.append(config.SIGNATURE_HTML)
    parts.append("</body></html>")

    return "\n".join(parts)


def render_plaintext_fallback(greeting: str, company_name: str) -> str:
    """Plain-text fallback for email clients that cannot render HTML."""
    bullets = "\n".join(f"  • {item}" for item in _JD_BULLETS)
    return (
        f"{greeting}\n\n"
        f"Greetings of the day from NMIMS, Bengaluru!\n\n"
        f"Hope you are safe and doing well.\n"
        f"As an AICTE-approved institution, NMIMS Bengaluru has established itself as a hub of academic "
        f"excellence and innovation within the dynamic landscape of Bengaluru. Our MBA program offers a "
        f"rigorous 102-credit curriculum across diverse specializations including Finance, Marketing, "
        f"IT & Operations, Analytics, Strategy, and HR.\n"
        f"As we prepare for the forthcoming Summer Internship and Final Placement Season, we are pleased "
        f"to invite your esteemed organization to engage with our student cohort.\n"
        f"To initiate the process, we kindly request you to share the role-specific details, which will "
        f"help us drive student interest and ensure a stronger fit between your requirements and our "
        f"students\u2019 capabilities.\n"
        f"We would require the Job Description comprising of the following details:\n\n"
        f"{bullets}\n\n"
        f"Also, please find the link to our Corporate Presentation and Placement Brochure for your kind perusal.\n"
        f"We look forward to partnering with {company_name} and welcoming your organization during our "
        f"Placement Season.\n"
        f"Kindly let us know in case of any concerns.\n\n"
        f"Best Regards,\nHarshul Varshney\nMember | Placement Committee\n"
        f"SVKM's Narsee Monjee Institute of Management Studies,\n"
        f"Bannerghatta Main Road, Bengaluru - 560083\n"
    )
