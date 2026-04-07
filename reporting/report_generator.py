"""
PDF Report Generator.

Generates a concise, customer-facing downloadable PDF report using ReportLab.
Internal diagnostics such as DOM structure, CTA aggressiveness, and tech stack
are intentionally excluded from the final report.
"""

import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
    Image,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

from utils.config import REPORTS_DIR
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Custom Styles ──────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

styles.add(
    ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontSize=24,
        spaceAfter=20,
        textColor=colors.HexColor("#1a1a2e"),
        alignment=TA_CENTER,
    )
)

styles.add(
    ParagraphStyle(
        name="SectionHeader",
        parent=styles["Heading1"],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor("#16213e"),
        borderWidth=1,
        borderColor=colors.HexColor("#0f3460"),
        borderPadding=(0, 0, 5, 0),
    )
)

styles.add(
    ParagraphStyle(
        name="SubHeader",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#0f3460"),
    )
)

styles.add(
    ParagraphStyle(
        name="BodyJustified",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
)

styles.add(
    ParagraphStyle(
        name="SmallText",
        parent=styles["BodyText"],
        fontSize=8,
        textColor=colors.HexColor("#666666"),
    )
)

# Table styling
HEADER_BG = colors.HexColor("#16213e")
HEADER_FG = colors.white
ALT_ROW_BG = colors.HexColor("#f0f0f5")
BORDER_COLOR = colors.HexColor("#cccccc")

TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
)


def generate_report(
    company_name: str,
    company_url: str,
    business_profile: dict,
    visual_profile: dict,
    dom_features: dict,
    competitors: list[dict],
    comparison: dict,
    executive_summary: str,
    local_competitors: list[dict] | None = None,
    global_competitors: list[dict] | None = None,
) -> str:
    """
    Generate a comprehensive PDF intelligence report.

    Args:
        company_name: Name of the analyzed company.
        company_url: URL of the analyzed company.
        business_profile: Structured business profile.
        visual_profile: Visual brand analysis profile.
        dom_features: DOM structural features.
        competitors: Combined list of competitor data dictionaries.
        comparison: Comparative analysis dictionary.
        executive_summary: Executive summary text.
        local_competitors: Local (Indian) competitor data.
        global_competitors: Global (international) competitor data.

    Returns:
        Path to the generated PDF file.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in company_name)[:50]
    filename = f"report_{safe_name}_{timestamp}.pdf"
    filepath = str(REPORTS_DIR / filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=20 * mm,
    )

    elements = []

    # ── Title Page ─────────────────────────────────────────────────────────
    elements.append(Spacer(1, 60))
    elements.append(Paragraph("Competitor Intelligence Report", styles["ReportTitle"]))
    elements.append(Spacer(1, 10))
    elements.append(
        Paragraph(
            f"<b>{_escape(company_name)}</b>",
            ParagraphStyle(
                "CompanyTitle",
                parent=styles["Title"],
                fontSize=18,
                textColor=colors.HexColor("#0f3460"),
                alignment=TA_CENTER,
            ),
        )
    )
    elements.append(Spacer(1, 5))
    elements.append(
        Paragraph(
            f"<i>{_escape(company_url)}</i>",
            ParagraphStyle(
                "URLStyle",
                parent=styles["Normal"],
                fontSize=10,
                textColor=colors.HexColor("#888888"),
                alignment=TA_CENTER,
            ),
        )
    )
    elements.append(Spacer(1, 20))
    elements.append(
        Paragraph(
            f"Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}",
            ParagraphStyle(
                "DateStyle",
                parent=styles["Normal"],
                fontSize=10,
                textColor=colors.HexColor("#888888"),
                alignment=TA_CENTER,
            ),
        )
    )
    elements.append(Spacer(1, 10))
    elements.append(
        HRFlowable(
            width="80%", color=colors.HexColor("#0f3460"), thickness=2, spaceAfter=20
        )
    )
    elements.append(PageBreak())

    # ── 1. Executive Summary ───────────────────────────────────────────────
    elements.append(Paragraph("1. Executive Summary", styles["SectionHeader"]))
    elements.append(Paragraph(_escape(executive_summary), styles["BodyJustified"]))
    elements.append(Spacer(1, 15))

    # ── 2. Business Profile ────────────────────────────────────────────────
    elements.append(Paragraph("2. Business Profile", styles["SectionHeader"]))
    try:
        elements.extend(_build_profile_section(business_profile))
    except Exception as e:
        logger.warning("Report section 'Business Profile' failed: %s", e)
        elements.append(
            Paragraph(
                "Business profile data could not be rendered.", styles["BodyJustified"]
            )
        )
    elements.append(Spacer(1, 10))

    # ── 3. Visual Brand Analysis ───────────────────────────────────────────
    elements.append(Paragraph("3. Visual Brand Analysis", styles["SectionHeader"]))
    try:
        elements.extend(_build_visual_section(visual_profile))
    except Exception as e:
        logger.warning("Report section 'Visual Analysis' failed: %s", e)
        elements.append(
            Paragraph(
                "Visual analysis data could not be rendered.", styles["BodyJustified"]
            )
        )
    elements.append(PageBreak())

    # Resolve scope lists — fall back to combined list if not provided
    _local = local_competitors if local_competitors is not None else []
    _global = global_competitors if global_competitors is not None else []
    # If neither was provided, treat all as global (backward compat)
    if not _local and not _global and competitors:
        _global = competitors

    # ── 5A. Local Competitor List ──────────────────────────────────────────
    elements.append(
        Paragraph(
            f"4A. Local Competitors — India ({len(_local)})",
            styles["SectionHeader"],
        )
    )
    if _local:
        try:
            elements.extend(_build_competitor_list(_local))
        except Exception as e:
            logger.warning("Report section 'Local Competitor List' failed: %s", e)
            elements.append(
                Paragraph(
                    "Local competitor list could not be rendered.",
                    styles["BodyJustified"],
                )
            )
    else:
        elements.append(
            Paragraph(
                "No local (Indian) competitors were discovered.",
                styles["BodyJustified"],
            )
        )
    elements.append(Spacer(1, 10))

    # ── 5B. Global Competitor List ─────────────────────────────────────────
    elements.append(
        Paragraph(
            f"4B. Global Competitors ({len(_global)})",
            styles["SectionHeader"],
        )
    )
    if _global:
        try:
            elements.extend(_build_competitor_list(_global))
        except Exception as e:
            logger.warning("Report section 'Global Competitor List' failed: %s", e)
            elements.append(
                Paragraph(
                    "Global competitor list could not be rendered.",
                    styles["BodyJustified"],
                )
            )
    else:
        elements.append(
            Paragraph("No global competitors were discovered.", styles["BodyJustified"])
        )
    elements.append(Spacer(1, 10))

    # ── 6A. Local Competitor Deep Profiles ─────────────────────────────────
    if _local:
        elements.append(
            Paragraph("5A. Local Competitor Deep Profiles", styles["SectionHeader"])
        )
        try:
            elements.extend(_build_competitor_profiles(_local))
        except Exception as e:
            logger.warning("Report section 'Local Competitor Profiles' failed: %s", e)
            elements.append(
                Paragraph(
                    "Local competitor profiles could not be rendered.",
                    styles["BodyJustified"],
                )
            )
        elements.append(Spacer(1, 10))

    # ── 6B. Global Competitor Deep Profiles ────────────────────────────────
    if _global:
        elements.append(
            Paragraph("5B. Global Competitor Deep Profiles", styles["SectionHeader"])
        )
        try:
            elements.extend(_build_competitor_profiles(_global))
        except Exception as e:
            logger.warning("Report section 'Global Competitor Profiles' failed: %s", e)
            elements.append(
                Paragraph(
                    "Global competitor profiles could not be rendered.",
                    styles["BodyJustified"],
                )
            )
    elements.append(PageBreak())

    # ── 7. Side-by-Side Comparison ─────────────────────────────────────────
    elements.append(Paragraph("6. Side-by-Side Comparison", styles["SectionHeader"]))
    try:
        elements.extend(
            _build_comparison_section(comparison, business_profile, competitors)
        )
    except Exception as e:
        logger.warning("Report section 'Comparison' failed: %s", e)
        elements.append(
            Paragraph("Comparison data could not be rendered.", styles["BodyJustified"])
        )
    elements.append(Spacer(1, 10))

    # ── 8. Strategic Insights ──────────────────────────────────────────────
    elements.append(
        Paragraph("7. Strategic Threat Assessment", styles["SectionHeader"])
    )
    try:
        elements.extend(_build_threats_section(comparison))
    except Exception as e:
        logger.warning("Report section 'Threats' failed: %s", e)
        elements.append(
            Paragraph(
                "Threat assessment could not be rendered.", styles["BodyJustified"]
            )
        )
    elements.append(Spacer(1, 10))

    # ── 9. Market Opportunities ────────────────────────────────────────────
    elements.append(Paragraph("8. White Space Opportunities", styles["SectionHeader"]))
    try:
        elements.extend(_build_opportunities_section(comparison))
    except Exception as e:
        logger.warning("Report section 'Opportunities' failed: %s", e)
        elements.append(
            Paragraph(
                "Opportunities data could not be rendered.", styles["BodyJustified"]
            )
        )
    elements.append(Spacer(1, 10))

    # ── 10. Recommendations ────────────────────────────────────────────────
    elements.append(Paragraph("9. Strategic Recommendations", styles["SectionHeader"]))
    try:
        elements.extend(_build_recommendations_section(comparison))
    except Exception as e:
        logger.warning("Report section 'Recommendations' failed: %s", e)
        elements.append(
            Paragraph("Recommendations could not be rendered.", styles["BodyJustified"])
        )

    # ── Footer ─────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 30))
    elements.append(HRFlowable(width="100%", color=BORDER_COLOR, thickness=1))
    elements.append(
        Paragraph(
            "Generated by AI-Powered Competitor Intelligence Engine",
            styles["SmallText"],
        )
    )

    # Build PDF
    doc.build(elements)
    logger.info("PDF report generated: %s", filepath)
    return filepath


def _sanitize_text(text: str) -> str:
    """
    Sanitize text for PDF rendering by removing problematic Unicode characters
    that can cause black dots or rendering issues.
    """
    if not isinstance(text, str):
        text = str(text)

    # Repair common mojibake sequences before further cleanup.
    if any(marker in text for marker in ("â", "Ã", "Â", "â€™", "â€œ", "â€")):
        try:
            text = text.encode("latin1", "ignore").decode("utf-8", "ignore")
        except Exception:
            pass

    # Remove lightweight markdown artifacts that occasionally leak through LLMs.
    text = (
        text.replace("**", "")
        .replace("__", "")
        .replace("`", "")
        .replace("### ", "")
        .replace("## ", "")
        .replace("# ", "")
    )

    # Replace common problematic Unicode characters with simple alternatives
    text = text.replace("\u2022", "-")  # Bullet point
    text = text.replace("\u2023", "-")  # Triangle bullet
    text = text.replace("\u2043", "-")  # Hyphen bullet
    text = text.replace("\u25cf", "*")  # Black circle
    text = text.replace("\u25cb", "*")  # White circle
    text = text.replace("\u25cc", "*")  # Dotted circle
    text = text.replace("\u25e6", "*")  # White bullet
    text = text.replace("\u2027", "*")  # Interpunct
    text = text.replace("\u2013", "-")  # En dash
    text = text.replace("\u2014", "-")  # Em dash
    text = text.replace("\u2010", "-")  # Hyphen
    text = text.replace("\u2011", "-")  # Non-breaking hyphen
    text = text.replace("\u2012", "-")  # Figure dash
    text = text.replace("\u2015", "-")  # Horizontal bar
    text = text.replace("\u2212", "-")  # Minus sign
    text = text.replace("\u00ad", "-")  # Soft hyphen
    text = text.replace("\u2018", "'")  # Left single quote
    text = text.replace("\u2019", "'")  # Right single quote
    text = text.replace("\u201c", '"')  # Left double quote
    text = text.replace("\u201d", '"')  # Right double quote
    text = text.replace("\u2026", "...")  # Ellipsis
    text = text.replace("\u20b9", "Rs.")  # Indian Rupee
    text = text.replace("\u00a0", " ")  # Non-breaking space
    text = text.replace("\u202f", " ")  # Narrow no-break space
    text = text.replace("\ufeff", "")  # BOM

    text = unicodedata.normalize("NFKC", text)

    # Remove control characters (0x00-0x1F) except \n, \r, \t
    cleaned = []
    for char in text:
        code = ord(char)
        if code < 32 and char not in ("\n", "\r", "\t"):
            continue  # Skip control characters
        elif code >= 32:
            cleaned.append(char)
    text = "".join(cleaned)

    # Convert any remaining problematic Unicode to ASCII without injecting '?'.
    text = text.encode("ascii", "ignore").decode("ascii")

    return text


def _escape(text: str) -> str:
    """Escape text for XML/HTML in ReportLab paragraphs."""
    if not isinstance(text, str):
        text = str(text)
    # First sanitize to remove problematic Unicode
    text = _sanitize_text(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _wrap(text: str, max_len: int = 0) -> str:
    """Escape text for table cells. ReportLab Paragraph handles word-wrapping."""
    text = str(text) if text else "N/A"
    return _escape(text)


def _build_profile_section(profile: dict) -> list:
    """Build the business profile table."""
    elements = []
    rows = [["Attribute", "Value"]]

    display_fields = [
        ("Brand Name", "brand_name"),
        ("Industry", "industry"),
        ("Target Customer", "target_customer"),
        ("Pricing Model", "pricing_model"),
        ("Positioning", "positioning_statement"),
        ("Value Proposition", "value_proposition"),
        ("Brand Tone", "brand_tone"),
        ("Monetization", "monetization_model"),
        ("Geography Focus", "geography_focus"),
        ("Marketing Style", "marketing_style"),
        ("Funnel Type", "funnel_type"),
        ("Content Marketing", "content_marketing_presence"),
    ]

    for label, key in display_fields:
        value = profile.get(key, "N/A")
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        rows.append(
            [
                Paragraph(f"<b>{_escape(label)}</b>", styles["Normal"]),
                Paragraph(_wrap(str(value), 120), styles["Normal"]),
            ]
        )

    # Array fields
    for label, key in [
        ("Products/Services", "products_services"),
        ("Key Features", "key_features"),
        ("Differentiation", "differentiation_claims"),
    ]:
        values = profile.get(key, [])
        if isinstance(values, list):
            formatted = (
                "- " + "\n- ".join(_escape(str(v)) for v in values) if values else "N/A"
            )
        else:
            formatted = _escape(str(values))
        rows.append(
            [
                Paragraph(f"<b>{_escape(label)}</b>", styles["Normal"]),
                Paragraph(formatted, styles["Normal"]),
            ]
        )

    table = Table(rows, colWidths=[120, 380])
    table.setStyle(TABLE_STYLE)
    elements.append(table)
    return elements


def _build_dom_section(dom_features: dict) -> list:
    """Build DOM features display."""
    elements = []
    rows = [["Feature", "Value"]]

    feature_labels = {
        "cta_button_count": "CTA Buttons",
        "forms_detected": "Forms Detected",
        "testimonial_blocks": "Testimonial Blocks",
        "pricing_tables": "Pricing Elements",
        "navigation_depth": "Navigation Depth",
        "section_count": "Content Sections",
        "video_presence": "Video Present",
        "social_proof_elements": "Social Proof Elements",
        "image_count": "Images",
        "heading_count": "Headings",
        "link_count": "Links",
        "has_chat_widget": "Chat Widget",
    }

    for key, label in feature_labels.items():
        value = dom_features.get(key, "N/A")
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        rows.append([_escape(label), _escape(str(value))])

    table = Table(rows, colWidths=[150, 350])
    table.setStyle(TABLE_STYLE)
    elements.append(table)
    return elements


def _build_visual_section(visual_profile: dict) -> list:
    """Build visual brand analysis section."""
    elements = []

    text_fields = [
        "visual_brand_personality",
        "color_psychology",
        "emotional_tone_visual",
    ]
    for field in text_fields:
        value = visual_profile.get(field, "N/A")
        label = field.replace("_", " ").title()
        elements.append(
            Paragraph(f"<b>{label}:</b> {_escape(str(value))}", styles["BodyJustified"])
        )

    # Score table
    score_fields = [
        ("Premium vs Mass", "premium_vs_mass_score"),
        ("Trust Signal", "trust_signal_score"),
        ("CTA Visual Strength", "CTA_visual_strength"),
        ("Design Modernity", "design_modernity_score"),
    ]

    rows = [["Metric", "Score (1-10)"]]
    for label, key in score_fields:
        score = visual_profile.get(key, "N/A")
        rows.append([_escape(label), _escape(str(score))])

    table = Table(rows, colWidths=[200, 300])
    table.setStyle(TABLE_STYLE)
    elements.append(Spacer(1, 8))
    elements.append(table)
    return elements


def _build_competitor_list(competitors: list[dict]) -> list:
    """Build competitor summary table."""
    elements = []
    rows = [["#", "Name", "URL", "Similarity Score"]]

    for i, comp in enumerate(competitors, 1):
        rows.append(
            [
                str(i),
                _escape(comp.get("name", "Unknown")),
                _escape(comp.get("url", "N/A")),
                f"{comp.get('similarity_score', 0):.2f}",
            ]
        )

    if len(rows) > 1:
        table = Table(rows, colWidths=[30, 130, 230, 110])
        table.setStyle(TABLE_STYLE)
        elements.append(table)
    else:
        elements.append(
            Paragraph("No competitors discovered.", styles["BodyJustified"])
        )

    return elements


def _build_competitor_profiles(competitors: list[dict]) -> list:
    """Build detailed competitor profile sections."""
    elements = []

    for i, comp in enumerate(competitors, 1):
        name = comp.get("name", f"Competitor {i}")
        elements.append(Paragraph(f"6.{i} {_escape(name)}", styles["SubHeader"]))

        profile = comp.get("profile", {})
        if profile:
            key_items = [
                ("Industry", profile.get("industry")),
                ("Target Customer", profile.get("target_customer")),
                ("Value Proposition", profile.get("value_proposition")),
                ("Pricing Model", profile.get("pricing_model")),
                ("Positioning", profile.get("positioning_statement")),
            ]
            for label, value in key_items:
                if value and value != "Not detected":
                    elements.append(
                        Paragraph(
                            f"<b>{label}:</b> {_wrap(str(value), 150)}",
                            styles["BodyJustified"],
                        )
                    )
        else:
            elements.append(
                Paragraph("Profile data not available.", styles["BodyJustified"])
            )

        elements.append(Spacer(1, 8))

    return elements


def _build_comparison_section(
    comparison: dict, profile: dict, competitors: list[dict]
) -> list:
    """Build side-by-side comparison section."""
    elements = []

    for field in [
        "positioning_comparison",
        "pricing_comparison",
        "brand_personality_differences",
        "marketing_strategy_differences",
    ]:
        value = comparison.get(field, "N/A")
        label = field.replace("_", " ").title()
        elements.append(Paragraph(f"<b>{label}</b>", styles["SubHeader"]))
        elements.append(Paragraph(_escape(str(value)), styles["BodyJustified"]))

    # Feature gap analysis
    gap = comparison.get("feature_gap_analysis", {})
    if isinstance(gap, dict):
        elements.append(Paragraph("<b>Feature Gap Analysis</b>", styles["SubHeader"]))
        for sub_key in [
            "input_company_unique_features",
            "competitor_unique_features",
            "common_features",
            "emerging_features",
        ]:
            items = gap.get(sub_key, [])
            label = sub_key.replace("_", " ").title()
            elements.append(Paragraph(f"<i>{label}:</i>", styles["Normal"]))
            if isinstance(items, list) and items:
                for item in items:
                    elements.append(
                        Paragraph(f"  • {_escape(str(item))}", styles["Normal"])
                    )
            else:
                elements.append(Paragraph("  None identified", styles["Normal"]))
            elements.append(Spacer(1, 4))

    return elements


def _build_threats_section(comparison: dict) -> list:
    """Build strategic threat assessment table."""
    elements = []
    threats = comparison.get("strategic_threat_assessment", [])

    if isinstance(threats, list) and threats:
        rows = [["Competitor", "Threat Level", "Reasoning", "Defense"]]
        for threat in threats:
            if isinstance(threat, dict):
                rows.append(
                    [
                        _escape(str(threat.get("competitor_name", "N/A"))),
                        _escape(str(threat.get("threat_level", "N/A"))),
                        Paragraph(
                            _wrap(str(threat.get("threat_reasoning", "N/A")), 100),
                            styles["Normal"],
                        ),
                        Paragraph(
                            _wrap(
                                str(threat.get("defensive_recommendation", "N/A")), 100
                            ),
                            styles["Normal"],
                        ),
                    ]
                )
        table = Table(rows, colWidths=[80, 65, 200, 155])
        table.setStyle(TABLE_STYLE)
        elements.append(table)
    else:
        elements.append(
            Paragraph("No threat assessment available.", styles["BodyJustified"])
        )

    return elements


def _build_opportunities_section(comparison: dict) -> list:
    """Build white space opportunities table."""
    elements = []
    opportunities = comparison.get("white_space_opportunities", [])

    if isinstance(opportunities, list) and opportunities:
        rows = [["Opportunity", "Rationale", "Effort", "Impact"]]
        for opp in opportunities:
            if isinstance(opp, dict):
                rows.append(
                    [
                        Paragraph(
                            _wrap(str(opp.get("opportunity", "N/A")), 80),
                            styles["Normal"],
                        ),
                        Paragraph(
                            _wrap(str(opp.get("rationale", "N/A")), 80),
                            styles["Normal"],
                        ),
                        _escape(str(opp.get("effort_estimate", "N/A"))),
                        _escape(str(opp.get("potential_impact", "N/A"))),
                    ]
                )
        table = Table(rows, colWidths=[170, 180, 70, 80])
        table.setStyle(TABLE_STYLE)
        elements.append(table)
    else:
        elements.append(
            Paragraph("No opportunities identified.", styles["BodyJustified"])
        )

    return elements


def _build_recommendations_section(comparison: dict) -> list:
    """Build strategic recommendations table."""
    elements = []
    recommendations = comparison.get("strategic_recommendations", [])

    if isinstance(recommendations, list) and recommendations:
        rows = [["Recommendation", "Priority", "Expected Impact", "Notes"]]
        for rec in recommendations:
            if isinstance(rec, dict):
                rows.append(
                    [
                        Paragraph(
                            _wrap(str(rec.get("recommendation", "N/A")), 80),
                            styles["Normal"],
                        ),
                        _escape(str(rec.get("priority", "N/A"))),
                        Paragraph(
                            _wrap(str(rec.get("expected_impact", "N/A")), 70),
                            styles["Normal"],
                        ),
                        Paragraph(
                            _wrap(str(rec.get("implementation_notes", "N/A")), 70),
                            styles["Normal"],
                        ),
                    ]
                )
        table = Table(rows, colWidths=[170, 70, 130, 130])
        table.setStyle(TABLE_STYLE)
        elements.append(table)
    else:
        elements.append(
            Paragraph("No recommendations available.", styles["BodyJustified"])
        )

    return elements
