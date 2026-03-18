"""
LLM Wrapper with Fallback Support

Provides a wrapper around Groq LLM calls with automatic fallback
to a secondary model when rate limits are hit.
"""

import nest_asyncio

nest_asyncio.apply()

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from pydantic import SecretStr

from utils.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_FALLBACK_MODEL,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Initialize primary LLM (GPT-OSS-120b)
primary_llm = ChatGroq(
    api_key=SecretStr(GROQ_API_KEY) if GROQ_API_KEY else None,
    model=GROQ_MODEL,
    temperature=0.3,
)

# Initialize fallback LLM (Llama 70b)
fallback_llm = ChatGroq(
    api_key=SecretStr(GROQ_API_KEY) if GROQ_API_KEY else None,
    model=GROQ_FALLBACK_MODEL,
    temperature=0.3,
)


def call_llm_with_fallback(
    messages: list[HumanMessage],
    max_tokens: int = 2048,
    temperature: float = 0.3,
    use_fallback: bool = True,
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
        response = primary_llm.invoke(
            messages, max_tokens=max_tokens, temperature=temperature
        )
        return response
    except Exception as e:
        error_str = str(e).lower()

        # Check if it's a rate limit error
        if "rate_limit" in error_str or "429" in error_str:
            if use_fallback:
                logger.warning(
                    "Primary LLM (%s) rate limited, falling back to %s",
                    GROQ_MODEL,
                    GROQ_FALLBACK_MODEL,
                )
                try:
                    response = fallback_llm.invoke(
                        messages, max_tokens=max_tokens, temperature=temperature
                    )
                    logger.info("Fallback LLM succeeded")
                    return response
                except Exception as fallback_error:
                    logger.error(
                        "Fallback LLM also failed: %s",
                        str(fallback_error)[:200],
                    )
                    raise
            else:
                logger.warning("Rate limit error, fallback disabled")
                raise
        else:
            # Other errors - don't fallback, just re-raise
            logger.error("LLM error (not rate limit): %s", str(e)[:200])
            raise
