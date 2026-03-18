"""
Utility helper functions: URL normalization, domain extraction,
retry decorator, and JSON validation.
"""

import hashlib
import json
import re
import time
import functools
from urllib.parse import urlparse, urlunparse, urljoin
from typing import Any, Callable, Optional, Union

from utils.logger import get_logger

logger = get_logger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize a URL by stripping query parameters, fragments,
    trailing slashes, and lowercasing the scheme/host.

    Args:
        url: Raw URL string.

    Returns:
        Normalized URL string.
    """
    parsed = urlparse(url)
    # Rebuild without query/fragment
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            "",  # params
            "",  # query
            "",  # fragment
        )
    )
    return normalized


def extract_domain(url: str) -> str:
    """
    Extract the domain (netloc) from a URL.

    Args:
        url: Full URL string.

    Returns:
        Domain string (e.g., 'example.com').
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def is_same_domain(url: str, base_domain: str) -> bool:
    """
    Check if a URL belongs to the same domain.

    Args:
        url: URL to check.
        base_domain: Reference domain.

    Returns:
        True if the URL's domain matches the base domain.
    """
    url_domain = extract_domain(url)
    return url_domain == base_domain or url_domain.endswith(f".{base_domain}")


def resolve_url(base_url: str, relative_url: str) -> str:
    """
    Resolve a relative URL against a base URL.

    Args:
        base_url: The base URL.
        relative_url: The relative URL to resolve.

    Returns:
        Absolute URL string.
    """
    return urljoin(base_url, relative_url)


def content_hash(text: str) -> str:
    """
    Generate a SHA-256 hash of text content for deduplication.

    Args:
        text: Text content to hash.

    Returns:
        Hex digest string.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_valid_url(url: str) -> bool:
    """
    Check if a string is a valid HTTP/HTTPS URL.

    Args:
        url: String to validate.

    Returns:
        True if valid URL.
    """
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def is_crawlable_url(url: str) -> bool:
    """
    Check if a URL points to a crawlable web page
    (excludes images, PDFs, etc.).

    Args:
        url: URL to check.

    Returns:
        True if the URL likely points to an HTML page.
    """
    skip_extensions = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".mp4",
        ".mp3",
        ".zip",
        ".tar",
        ".gz",
        ".exe",
        ".dmg",
        ".css",
        ".js",
        ".xml",
        ".json",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    }
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    return not any(path_lower.endswith(ext) for ext in skip_extensions)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 2.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator that retries a function with exponential backoff.
    Handles Groq RateLimitError specially by respecting retry_after.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        backoff_factor: Multiplier for delay on each retry.
        exceptions: Tuple of exception types to catch.

    Returns:
        Decorated function.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(
                            "Function %s failed after %d attempts: %s",
                            func.__name__,
                            max_retries,
                            e,
                        )
                        raise

                    # Check if this is a Groq rate limit error
                    actual_delay = delay
                    error_type = type(e).__name__
                    if "RateLimitError" in error_type:
                        # Try to extract retry_after from the error
                        retry_after = getattr(e, "retry_after", None)
                        if retry_after and isinstance(retry_after, (int, float)):
                            actual_delay = max(float(retry_after), delay)
                            logger.warning(
                                "Rate limited on %s. Waiting %.1fs (retry_after=%.1fs)",
                                func.__name__,
                                actual_delay,
                                float(retry_after),
                            )
                        else:
                            # Default longer wait for rate limits
                            actual_delay = max(delay, 10.0)
                            logger.warning(
                                "Rate limited on %s. Waiting %.1fs",
                                func.__name__,
                                actual_delay,
                            )
                    else:
                        logger.warning(
                            "Attempt %d/%d for %s failed: %s. Retrying in %.1fs...",
                            attempt,
                            max_retries,
                            func.__name__,
                            e,
                            actual_delay,
                        )

                    time.sleep(actual_delay)
                    delay *= backoff_factor

        return wrapper

    return decorator


def validate_json_schema(data: dict, required_keys: list[str]) -> bool:
    """
    Validate that a dictionary contains all required keys.

    Args:
        data: Dictionary to validate.
        required_keys: List of keys that must be present.

    Returns:
        True if all required keys are present.
    """
    missing = [k for k in required_keys if k not in data]
    if missing:
        logger.warning("Missing required keys: %s", missing)
        return False
    return True


def safe_json_parse(text: str) -> Optional[Any]:
    """
    Safely parse a JSON string, handling common issues like
    markdown code fences around JSON AND truncated output from LLMs.

    Strategy:
        1. Strip markdown code fences
        2. Try standard json.loads
        3. If that fails, attempt to repair truncated JSON by
           closing unclosed brackets/braces

    Args:
        text: String potentially containing JSON.

    Returns:
        Parsed dict, list, or other JSON object, or None if parsing fails.
    """
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    # Attempt 1: Standard parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 2: Repair truncated JSON
    repaired = _repair_truncated_json(cleaned)
    if repaired is not None:
        try:
            result = json.loads(repaired)
            logger.info("Successfully parsed JSON after truncation repair")
            return result
        except json.JSONDecodeError:
            pass

    # Attempt 3: Extract the first JSON object from the text
    match = re.search(r"\{", cleaned)
    if match:
        substring = cleaned[match.start() :]
        repaired = _repair_truncated_json(substring)
        if repaired is not None:
            try:
                result = json.loads(repaired)
                logger.info("Successfully parsed JSON after extraction + repair")
                return result
            except json.JSONDecodeError:
                pass

    logger.warning("All JSON parse strategies failed for text: %s", cleaned[:200])
    return None


def _repair_truncated_json(text: str) -> Optional[str]:
    """
    Attempt to repair truncated JSON by closing unclosed brackets and braces.

    Handles cases where LLM output gets cut off mid-token, leaving
    incomplete strings, trailing commas, or unclosed structures.

    Args:
        text: Potentially truncated JSON string.

    Returns:
        Repaired JSON string, or None if repair is not possible.
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Must start with { or [ to be valid JSON
    if text[0] not in ("{", "["):
        return None

    # Track bracket state
    stack = []
    in_string = False
    escape_next = False
    i = 0

    while i < len(text):
        char = text[i]

        if escape_next:
            escape_next = False
            i += 1
            continue

        if char == "\\" and in_string:
            escape_next = True
            i += 1
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            i += 1
            continue

        if not in_string:
            if char in ("{", "["):
                stack.append(char)
            elif char == "}":
                if stack and stack[-1] == "{":
                    stack.pop()
            elif char == "]":
                if stack and stack[-1] == "[":
                    stack.pop()

        i += 1

    # If already balanced, no repair needed
    if not stack and not in_string:
        return text

    repaired = text

    # If we're inside an unclosed string, close it
    if in_string:
        repaired += '"'

    # Remove any trailing partial tokens: commas, colons, partial keys
    # Strip trailing whitespace, commas, colons after closing the string
    repaired = re.sub(r"[,:\s]+$", "", repaired)

    # Close all unclosed brackets/braces in reverse order
    for bracket in reversed(stack):
        if bracket == "{":
            repaired += "}"
        elif bracket == "[":
            repaired += "]"

    return repaired


def truncate_text(text: str, max_chars: int = 5000) -> str:
    """
    Truncate text to a maximum number of characters.

    Args:
        text: Input text.
        max_chars: Maximum character count.

    Returns:
        Truncated text string.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
