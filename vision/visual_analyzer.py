"""
Visual Intelligence Module.

Sends homepage screenshots to OpenRouter vision models to extract
a structured visual brand profile including color psychology,
design modernity, trust signals, and emotional tone.
"""

import base64
import json
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from utils.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_VISION_MODEL,
    OPENROUTER_MAX_RETRIES,
    OPENROUTER_APP_NAME,
    OPENROUTER_HTTP_REFERER,
)
from utils.helpers import safe_json_parse, retry_with_backoff
from utils.logger import get_logger

logger = get_logger(__name__)

_vision_headers = {}
if OPENROUTER_HTTP_REFERER:
    _vision_headers["HTTP-Referer"] = OPENROUTER_HTTP_REFERER
if OPENROUTER_APP_NAME:
    _vision_headers["X-Title"] = OPENROUTER_APP_NAME


def _build_vision_llm() -> ChatOpenAI:
    """Create the OpenRouter vision client lazily to avoid import-time crashes."""
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "Missing OpenRouter API key. Set OPENROUTER_API_KEY in .env."
        )
    return ChatOpenAI(
        api_key=OPENROUTER_API_KEY or None,
        base_url=OPENROUTER_BASE_URL,
        model=OPENROUTER_VISION_MODEL,
        temperature=0.2,
        default_headers=_vision_headers or None,
    )

# Required keys in the visual profile output
VISUAL_PROFILE_KEYS = [
    "visual_brand_personality",
    "color_psychology",
    "premium_vs_mass_score",
    "trust_signal_score",
    "CTA_visual_strength",
    "design_modernity_score",
    "emotional_tone_visual",
]

VISUAL_ANALYSIS_PROMPT = """You are an expert brand analyst and UX designer. Analyze this website screenshot and provide a structured visual brand profile.

You MUST return ONLY a valid JSON object with these exact keys:

{
    "visual_brand_personality": "A 2-3 sentence description of the brand's visual personality (e.g., 'Modern, minimalist, and tech-forward with clean typography and generous whitespace.')",
    "color_psychology": "Description of the color palette and its psychological implications (e.g., 'Dominated by blues and whites conveying trust and professionalism.')",
    "premium_vs_mass_score": <float between 1.0 and 10.0 where 10 = ultra premium>,
    "trust_signal_score": <float between 1.0 and 10.0 where 10 = extremely trustworthy>,
    "CTA_visual_strength": <float between 1.0 and 10.0 where 10 = very aggressive CTAs>,
    "design_modernity_score": <float between 1.0 and 10.0 where 10 = cutting edge modern>,
    "emotional_tone_visual": "The emotional tone conveyed by the visual design (e.g., 'Confident, approachable, and innovative')"
}

IMPORTANT: Return ONLY the JSON object. No markdown, no explanations, no code fences."""


def analyze_screenshot(screenshot_path: str) -> dict:
    """
    Analyze a website screenshot using an OpenRouter vision model.

    Args:
        screenshot_path: Path to the screenshot image file.

    Returns:
        Dictionary containing the visual brand profile.
    """
    if not Path(screenshot_path).exists():
        logger.warning("Screenshot not found: %s", screenshot_path)
        return _empty_visual_profile()

    if not OPENROUTER_API_KEY:
        logger.warning(
            "OpenRouter vision disabled because no API key is configured; "
            "returning empty visual profile"
        )
        return _empty_visual_profile()

    return _call_vision(screenshot_path)


@retry_with_backoff(max_retries=OPENROUTER_MAX_RETRIES, base_delay=2.0)
def _call_vision(screenshot_path: str) -> dict:
    """
    Call the OpenRouter vision API with the screenshot and parse the result.

    Args:
        screenshot_path: Path to the screenshot image file.

    Returns:
        Parsed visual profile dictionary.

    Raises:
        ValueError: If the response cannot be parsed into valid JSON.
    """
    # Load and encode the image as base64
    with open(screenshot_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    # Determine MIME type
    ext = Path(screenshot_path).suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/png")

    # Use LangChain ChatOpenAI against OpenRouter with image content.
    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": VISUAL_ANALYSIS_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_data}",
                    },
                },
            ]
        )
    ]
    response = _build_vision_llm().invoke(messages, max_tokens=1024)

    text = response.content
    result = safe_json_parse(text)
    if result is None:
        raise ValueError(f"Failed to parse vision response: {text[:200]}")

    # Validate required keys
    missing = [k for k in VISUAL_PROFILE_KEYS if k not in result]
    if missing:
        raise ValueError(f"Missing keys in visual profile: {missing}")

    logger.info("Visual analysis complete for: %s", screenshot_path)
    return result


def _empty_visual_profile() -> dict:
    """Return an empty/default visual profile."""
    return {
        "visual_brand_personality": "Not available",
        "color_psychology": "Not available",
        "premium_vs_mass_score": 5.0,
        "trust_signal_score": 5.0,
        "CTA_visual_strength": 5.0,
        "design_modernity_score": 5.0,
        "emotional_tone_visual": "Not available",
    }
