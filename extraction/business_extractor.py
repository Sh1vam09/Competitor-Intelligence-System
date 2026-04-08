"""
Structured Business Extraction Module.

Uses OpenRouter (via LangChain) to extract a comprehensive structured business profile
from crawled and processed website text. Enforces strict JSON schema
validation with retry on malformed output.
"""

import json

from langchain_core.messages import HumanMessage

from utils.config import OPENROUTER_MAX_RETRIES
from utils.helpers import safe_json_parse, retry_with_backoff, truncate_text
from utils.llm_wrapper import call_llm_with_fallback
from utils.logger import get_logger

logger = get_logger(__name__)

# Required keys in the business profile output
BUSINESS_PROFILE_KEYS = [
    "brand_name",
    "industry",
    "target_customer",
    "products_services",
    "pricing_model",
    "positioning_statement",
    "value_proposition",
    "brand_tone",
    "monetization_model",
    "geography_focus",
    "key_features",
    "differentiation_claims",
    "marketing_style",
    "funnel_type",
    "tech_stack_detected",
    "CTA_aggressiveness_score",
    "content_marketing_presence",
]

EXTRACTION_PROMPT = """You are an expert business analyst. Analyze the following website content and extract a comprehensive structured business profile.

WEBSITE CONTENT:
{content}

DOM STRUCTURAL FEATURES:
{dom_features}

You MUST return ONLY a valid JSON object with these exact keys:

{{
    "brand_name": "The company/brand name",
    "industry": "Primary industry or sector",
    "target_customer": "Description of the target customer/audience",
    "products_services": ["List of main products or services offered"],
    "pricing_model": "Pricing model description (e.g., 'Freemium with paid tiers', 'Subscription-based', 'One-time purchase')",
    "positioning_statement": "How the brand positions itself in the market (2-3 sentences)",
    "value_proposition": "Core value proposition (1-2 sentences)",
    "brand_tone": "Brand communication tone (e.g., 'Professional and authoritative', 'Casual and friendly')",
    "monetization_model": "How the business makes money",
    "geography_focus": "Geographic focus or target markets",
    "key_features": ["List of key features or capabilities highlighted"],
    "differentiation_claims": ["List of specific differentiation claims or unique selling points"],
    "marketing_style": "Description of marketing approach and style",
    "funnel_type": "Type of sales/marketing funnel (e.g., 'Product-led growth', 'Sales-led', 'Content marketing funnel')",
    "tech_stack_detected": ["Any technologies, platforms, or tools mentioned or detected"],
    "CTA_aggressiveness_score": <float between 1.0 and 10.0 where 10 = extremely aggressive CTAs>,
    "content_marketing_presence": "Description of content marketing efforts (blog, resources, guides, etc.)"
}}

IMPORTANT RULES:
1. Return ONLY the JSON object. No markdown, no explanations, no code fences.
2. If information is not available, use "Not detected" for strings, empty list [] for arrays, and 5.0 for scores.
3. Be specific and evidence-based — quote from the content where possible.
4. products_services, key_features, differentiation_claims, and tech_stack_detected MUST be arrays.
5. Keep every field concise. Do not include long quotes or long product lists.
6. Always include all keys, even when the value is "Not detected" or []."""


def _normalize_business_profile(result: dict) -> dict:
    """Fill missing fields with safe defaults and normalize output types."""
    normalized = _empty_business_profile()
    if isinstance(result, dict):
        normalized.update(result)

    array_fields = [
        "products_services",
        "key_features",
        "differentiation_claims",
        "tech_stack_detected",
    ]
    for field in array_fields:
        value = normalized.get(field)
        if isinstance(value, list):
            normalized[field] = [str(item).strip() for item in value if str(item).strip()]
        elif value in (None, "", "Not detected"):
            normalized[field] = []
        else:
            normalized[field] = [str(value).strip()]

    score = normalized.get("CTA_aggressiveness_score", 5.0)
    try:
        normalized["CTA_aggressiveness_score"] = float(score)
    except (TypeError, ValueError):
        normalized["CTA_aggressiveness_score"] = 5.0

    for key in BUSINESS_PROFILE_KEYS:
        if key == "CTA_aggressiveness_score" or key in array_fields:
            continue
        value = normalized.get(key)
        if value is None or value == "":
            normalized[key] = "Not detected"
        else:
            normalized[key] = str(value).strip()

    return normalized


def extract_business_profile(
    text_chunks: list[str],
    dom_features: dict,
) -> dict:
    """
    Extract a structured business profile from website content.

    Args:
        text_chunks: List of text chunks from the processed website.
        dom_features: DOM structural features dictionary.

    Returns:
        Structured business profile dictionary.
    """
    # Combine chunks (limit total content to avoid token limits)
    combined_text = "\n\n".join(text_chunks)
    combined_text = truncate_text(combined_text, max_chars=12000)

    dom_features_str = json.dumps(dom_features, indent=2)

    return _call_llm_extraction(combined_text, dom_features_str)


@retry_with_backoff(max_retries=OPENROUTER_MAX_RETRIES, base_delay=2.0)
def _call_llm_extraction(content: str, dom_features: str) -> dict:
    """
    Call the configured OpenRouter model for structured business extraction.

    Args:
        content: Combined website text content.
        dom_features: JSON string of DOM features.

    Returns:
        Parsed business profile dictionary.

    Raises:
        ValueError: If the response cannot be parsed or is missing keys.
    """
    prompt = EXTRACTION_PROMPT.format(
        content=content,
        dom_features=dom_features,
    )

    # Use the shared OpenRouter wrapper with fallback.
    messages = [HumanMessage(content=prompt)]
    response = call_llm_with_fallback(
        messages,
        max_tokens=2048,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    text = response.content
    result = safe_json_parse(text)
    if result is None:
        raise ValueError(f"Failed to parse LLM extraction response: {text[:300]}")

    result = _normalize_business_profile(result)

    logger.info("Business profile extracted: %s", result.get("brand_name", "Unknown"))
    return result


def _empty_business_profile() -> dict:
    """Return an empty/default business profile."""
    return {key: "Not detected" if key != "CTA_aggressiveness_score" else 5.0
            for key in BUSINESS_PROFILE_KEYS}

"""
Structured Business Extraction Module.

Uses OpenRouter (via LangChain) to extract a comprehensive structured business profile
from crawled and processed website text. Enforces strict JSON schema
validation with retry on malformed output.
"""

import json

from langchain_core.messages import HumanMessage

from utils.config import OPENROUTER_MAX_RETRIES
from utils.helpers import safe_json_parse, retry_with_backoff, truncate_text
from utils.llm_wrapper import call_llm_with_fallback
from utils.logger import get_logger

logger = get_logger(__name__)

# Required keys in the business profile output
BUSINESS_PROFILE_KEYS = [
    "brand_name",
    "industry",
    "target_customer",
    "products_services",
    "pricing_model",
    "positioning_statement",
    "value_proposition",
    "brand_tone",
    "monetization_model",
    "geography_focus",
    "key_features",
    "differentiation_claims",
    "marketing_style",
    "funnel_type",
    "tech_stack_detected",
    "CTA_aggressiveness_score",
    "content_marketing_presence",
]

EXTRACTION_PROMPT = """You are an expert business analyst. Analyze the following website content and extract a comprehensive structured business profile.

WEBSITE CONTENT:
{content}

DOM STRUCTURAL FEATURES:
{dom_features}

You MUST return ONLY a valid JSON object with these exact keys:

{{
    "brand_name": "The company/brand name",
    "industry": "Primary industry or sector",
    "target_customer": "Description of the target customer/audience",
    "products_services": ["List of main products or services offered"],
    "pricing_model": "Pricing model description (e.g., 'Freemium with paid tiers', 'Subscription-based', 'One-time purchase')",
    "positioning_statement": "How the brand positions itself in the market (2-3 sentences)",
    "value_proposition": "Core value proposition (1-2 sentences)",
    "brand_tone": "Brand communication tone (e.g., 'Professional and authoritative', 'Casual and friendly')",
    "monetization_model": "How the business makes money",
    "geography_focus": "Geographic focus or target markets",
    "key_features": ["List of key features or capabilities highlighted"],
    "differentiation_claims": ["List of specific differentiation claims or unique selling points"],
    "marketing_style": "Description of marketing approach and style",
    "funnel_type": "Type of sales/marketing funnel (e.g., 'Product-led growth', 'Sales-led', 'Content marketing funnel')",
    "tech_stack_detected": ["Any technologies, platforms, or tools mentioned or detected"],
    "CTA_aggressiveness_score": <float between 1.0 and 10.0 where 10 = extremely aggressive CTAs>,
    "content_marketing_presence": "Description of content marketing efforts (blog, resources, guides, etc.)"
}}

IMPORTANT RULES:
1. Return ONLY the JSON object. No markdown, no explanations, no code fences.
2. If information is not available, use "Not detected" for strings, empty list [] for arrays, and 5.0 for scores.
3. Be specific and evidence-based — quote from the content where possible.
4. products_services, key_features, differentiation_claims, and tech_stack_detected MUST be arrays.
5. Keep every field concise. Do not include long quotes or long product lists.
6. Always include all keys, even when the value is "Not detected" or []."""


def extract_business_profile(
    text_chunks: list[str],
    dom_features: dict,
) -> dict:
    """
    Extract a structured business profile from website content.

    Args:
        text_chunks: List of text chunks from the processed website.
        dom_features: DOM structural features dictionary.

    Returns:
        Structured business profile dictionary.
    """
    # Combine chunks (limit total content to avoid token limits)
    combined_text = "\n\n".join(text_chunks)
    combined_text = truncate_text(combined_text, max_chars=12000)

    dom_features_str = json.dumps(dom_features, indent=2)

    return _call_llm_extraction(combined_text, dom_features_str)


@retry_with_backoff(max_retries=OPENROUTER_MAX_RETRIES, base_delay=2.0)
def _call_llm_extraction(content: str, dom_features: str) -> dict:
    """
    Call the configured OpenRouter model for structured business extraction.

    Args:
        content: Combined website text content.
        dom_features: JSON string of DOM features.

    Returns:
        Parsed business profile dictionary.

    Raises:
        ValueError: If the response cannot be parsed or is missing keys.
    """
    prompt = EXTRACTION_PROMPT.format(
        content=content,
        dom_features=dom_features,
    )

    # Use the shared OpenRouter wrapper with fallback.
    messages = [HumanMessage(content=prompt)]
    response = call_llm_with_fallback(
        messages,
        max_tokens=2048,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    text = response.content
    result = safe_json_parse(text)
    if result is None:
        raise ValueError(f"Failed to parse LLM extraction response: {text[:300]}")

    result = _normalize_business_profile(result)

    logger.info("Business profile extracted: %s", result.get("brand_name", "Unknown"))
    return result


def _empty_business_profile() -> dict:
    """Return an empty/default business profile."""
    return {
        key: "Not detected" if key != "CTA_aggressiveness_score" else 5.0
        for key in BUSINESS_PROFILE_KEYS
    }
