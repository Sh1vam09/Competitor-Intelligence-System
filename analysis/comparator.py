"""
Comparative Intelligence Analysis Module.

Uses OpenRouter (via LangChain) to generate structured competitive analysis
comparing the input company against discovered competitors.
Produces strategic insights, gap analysis, and recommendations.
"""

import json

from langchain_core.messages import HumanMessage

from utils.config import OPENROUTER_MAX_RETRIES
from utils.helpers import safe_json_parse, retry_with_backoff, truncate_text
from utils.llm_wrapper import call_llm_with_fallback
from utils.logger import get_logger

logger = get_logger(__name__)

COMPARISON_KEYS = [
    "positioning_comparison",
    "pricing_comparison",
    "feature_gap_analysis",
    "brand_personality_differences",
    "marketing_strategy_differences",
    "market_saturation_estimate",
    "strategic_threat_assessment",
    "white_space_opportunities",
    "strategic_recommendations",
]

COMPARISON_PROMPT = """You are a senior competitive intelligence strategist. Analyze the following company and its competitors to produce a comprehensive strategic intelligence report.

INPUT COMPANY PROFILE:
{input_profile}

INPUT COMPANY VISUAL PROFILE:
{input_visual}

COMPETITOR PROFILES:
{competitor_profiles}

Generate a structured comparative intelligence analysis. You MUST return ONLY a valid JSON object with these exact keys:

{{
    "positioning_comparison": "Detailed comparison of how each company positions itself in the market. Include specific positioning statements and differentiation strategies.",
    "pricing_comparison": "Comparison of pricing models, tiers, and strategies across all companies. Note any pricing advantages or disadvantages.",
    "feature_gap_analysis": {{
        "input_company_unique_features": ["Features the input company has that competitors lack"],
        "competitor_unique_features": ["Features competitors have that the input company lacks"],
        "common_features": ["Features shared across most competitors"],
        "emerging_features": ["Features that are becoming table stakes in the industry"]
    }},
    "brand_personality_differences": "Analysis of how brand personalities differ — tone, visual identity, communication style, target audience appeal.",
    "marketing_strategy_differences": "Comparison of marketing approaches — channels used, content strategy, merchandising, offers, and customer acquisition style.",
    "market_saturation_estimate": {{
        "saturation_level": "<low/medium/high>",
        "reasoning": "Why you assessed this saturation level",
        "growth_trajectory": "Assessment of market growth direction"
    }},
    "strategic_threat_assessment": [
        {{
            "competitor_name": "Name",
            "threat_level": "<low/medium/high/critical>",
            "threat_reasoning": "Why this competitor is a threat",
            "defensive_recommendation": "How to defend against this threat"
        }}
    ],
    "white_space_opportunities": [
        {{
            "opportunity": "Description of the market gap or opportunity",
            "rationale": "Why this opportunity exists",
            "effort_estimate": "<low/medium/high>",
            "potential_impact": "<low/medium/high>"
        }}
    ],
    "strategic_recommendations": [
        {{
            "recommendation": "Specific actionable recommendation",
            "priority": "<immediate/short-term/long-term>",
            "expected_impact": "What impact this recommendation would have",
            "implementation_notes": "Brief notes on how to implement"
        }}
    ]
}}

IMPORTANT:
1. Return ONLY the JSON object. No markdown, no code fences.
2. Be specific and actionable — avoid generic advice.
3. Reference specific companies by name in your analysis.
4. Base all assessments strictly on the provided profile data.
5. Do NOT invent unsupported claims, market trends, or strategic ideas. If evidence is weak, say less.
6. Do NOT use customer-irrelevant diagnostics such as DOM metrics, CTA aggressiveness scores, or tech-stack trivia.
7. Every threat, opportunity, and recommendation must clearly tie back to a concrete competitor fact from the provided profiles."""


def generate_comparative_analysis(
    input_profile: dict,
    input_visual_profile: dict,
    competitor_profiles: list[dict],
) -> dict:
    """
    Generate a comprehensive comparative intelligence analysis
    using the configured OpenRouter model.

    Args:
        input_profile: Structured business profile of the input company.
        input_visual_profile: Visual brand profile of the input company.
        competitor_profiles: List of competitor profile dictionaries,
            each containing 'name', 'url', 'profile', and optionally 'visual_profile'.

    Returns:
        Structured comparative analysis dictionary.
    """
    input_profile_str = truncate_text(json.dumps(input_profile, indent=2), 4000)
    input_visual_str = truncate_text(json.dumps(input_visual_profile, indent=2), 1500)
    comp_entries = []
    for i, comp in enumerate(competitor_profiles, 1):
        entry = f"--- Competitor {i}: {comp.get('name', 'Unknown')} ({comp.get('url', '')}) ---\n"
        profile_data = comp.get("profile", {})
        entry += truncate_text(json.dumps(profile_data, indent=2), 3000)
        if comp.get("visual_profile"):
            entry += f"\nVisual Profile: {truncate_text(json.dumps(comp['visual_profile'], indent=2), 800)}"
        comp_entries.append(entry)

    competitor_profiles_str = "\n\n".join(comp_entries)
    competitor_profiles_str = truncate_text(competitor_profiles_str, 12000)

    return _call_llm_comparison(
        input_profile_str, input_visual_str, competitor_profiles_str
    )


@retry_with_backoff(max_retries=OPENROUTER_MAX_RETRIES, base_delay=3.0)
def _call_llm_comparison(
    input_profile: str,
    input_visual: str,
    competitor_profiles: str,
) -> dict:
    """
    Call the configured OpenRouter model for comparative analysis.

    Raises:
        ValueError: If response is malformed after all repair attempts.
    """
    prompt = COMPARISON_PROMPT.format(
        input_profile=input_profile,
        input_visual=input_visual,
        competitor_profiles=competitor_profiles,
    )

    # Use the shared OpenRouter wrapper with fallback.
    messages = [HumanMessage(content=prompt)]
    response = call_llm_with_fallback(messages, max_tokens=16384, temperature=0.2)

    text = response.content
    result = safe_json_parse(text)
    if result is None:
        raise ValueError(f"Failed to parse comparison response: {text[:500]}")

    # Fill any missing keys with defaults rather than failing
    result = _fill_missing_keys(result)

    logger.info("Comparative analysis generated successfully")
    return result


def _fill_missing_keys(result: dict) -> dict:
    """
    Ensure all required comparison keys exist in the result.
    Missing keys get sensible defaults so the pipeline never crashes.
    """
    defaults = {
        "positioning_comparison": "Analysis not available.",
        "pricing_comparison": "Analysis not available.",
        "feature_gap_analysis": {
            "input_company_unique_features": [],
            "competitor_unique_features": [],
            "common_features": [],
            "emerging_features": [],
        },
        "brand_personality_differences": "Analysis not available.",
        "marketing_strategy_differences": "Analysis not available.",
        "market_saturation_estimate": {
            "saturation_level": "unknown",
            "reasoning": "Could not be determined due to incomplete data.",
            "growth_trajectory": "unknown",
        },
        "strategic_threat_assessment": [],
        "white_space_opportunities": [],
        "strategic_recommendations": [],
    }
    for key in COMPARISON_KEYS:
        if key not in result:
            logger.warning("Missing comparison key '%s', using default", key)
            result[key] = defaults.get(key, "Analysis not available.")
    return result


def generate_executive_summary(
    input_profile: dict,
    comparison: dict,
    num_competitors: int,
) -> str:
    """
    Generate a concise executive summary of the competitive analysis.

    Args:
        input_profile: Input company business profile.
        comparison: Full comparative analysis dictionary.
        num_competitors: Number of competitors analyzed.

    Returns:
        Executive summary string.
    """
    try:
        prompt = f"""Write a concise 3-4 paragraph executive summary of this competitive intelligence analysis.

Company: {input_profile.get("brand_name", "Unknown")}
Industry: {input_profile.get("industry", "Unknown")}
Number of competitors analyzed: {num_competitors}

Key findings:
- Market saturation: {json.dumps(comparison.get("market_saturation_estimate", {}), indent=2)}
- White space opportunities: {len(comparison.get("white_space_opportunities", []))} identified
- Strategic recommendations: {len(comparison.get("strategic_recommendations", []))} provided

Positioning: {comparison.get("positioning_comparison", "N/A")[:500]}

Write in a professional, analytical tone. Be specific and data-driven.
Do not use markdown formatting. Do not introduce new claims or recommendations beyond the provided analysis.
Return only the summary text, no JSON."""

        # Use the shared OpenRouter wrapper with fallback.
        messages = [HumanMessage(content=prompt)]
        response = call_llm_with_fallback(messages, max_tokens=1024, temperature=0.3)
        return response.content.strip()

    except Exception as e:
        logger.warning("Executive summary generation failed: %s", e)
        brand = input_profile.get("brand_name", "The company")
        return (
            f"{brand} operates in the {input_profile.get('industry', 'unknown')} industry. "
            f"Analysis of {num_competitors} competitors was conducted. "
            f"See detailed sections below for findings and recommendations."
        )
