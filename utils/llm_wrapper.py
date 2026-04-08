"""
LLM Wrapper with Fallback Support.

Provides a wrapper around OpenRouter LLM calls with automatic fallback
to a secondary model when rate limits or provider-capacity errors are hit.
"""

import nest_asyncio

nest_asyncio.apply()

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from utils.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    OPENROUTER_FALLBACK_MODEL,
    OPENROUTER_APP_NAME,
    OPENROUTER_HTTP_REFERER,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def _default_headers() -> dict:
    """Build optional OpenRouter headers for request attribution."""
    headers: dict[str, str] = {}
    if OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = OPENROUTER_HTTP_REFERER
    if OPENROUTER_APP_NAME:
        headers["X-Title"] = OPENROUTER_APP_NAME
    return headers


def _build_llm(model: str, temperature: float = 0.3) -> ChatOpenAI:
    """Create a ChatOpenAI client pointed at OpenRouter."""
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "Missing OpenRouter API key. Set OPENROUTER_API_KEY in .env."
        )
    return ChatOpenAI(
        api_key=OPENROUTER_API_KEY or None,
        base_url=OPENROUTER_BASE_URL,
        model=model,
        temperature=temperature,
        default_headers=_default_headers() or None,
    )


def call_llm_with_fallback(
    messages: list[HumanMessage],
    max_tokens: int = 2048,
    temperature: float = 0.3,
    use_fallback: bool = True,
    **invoke_kwargs,
):
    """
    Call LLM with automatic fallback on rate limit errors.

    Args:
        messages: List of HumanMessage objects to send to LLM
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        use_fallback: Whether to use fallback model on rate limit

    Returns:
        Response from LLM (primary or fallback)

    Raises:
        Exception: If both models fail
    """
    try:
        response = _build_llm(OPENROUTER_MODEL, temperature=temperature).invoke(
            messages,
            max_tokens=max_tokens,
            **invoke_kwargs,
        )
        return response
    except Exception as e:
        error_str = str(e).lower()

        # Check if it is a provider-capacity / rate-limit style error.
        if any(
            token in error_str
            for token in ("rate_limit", "429", "503", "over capacity")
        ):
            if use_fallback:
                logger.warning(
                    "Primary LLM (%s) unavailable, falling back to %s",
                    OPENROUTER_MODEL,
                    OPENROUTER_FALLBACK_MODEL,
                )
                try:
                    response = _build_llm(
                        OPENROUTER_FALLBACK_MODEL,
                        temperature=temperature,
                    ).invoke(messages, max_tokens=max_tokens, **invoke_kwargs)
                    logger.info("Fallback LLM succeeded")
                    return response
                except Exception as fallback_error:
                    logger.error(
                        "Fallback LLM also failed: %s",
                        str(fallback_error)[:200],
                    )
                    raise
            else:
                logger.warning("Provider error, fallback disabled")
                raise
        else:
            logger.error("LLM error (not fallback-eligible): %s", str(e)[:200])
            raise
