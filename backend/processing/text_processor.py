"""
Text processing module: boilerplate removal, text cleanup,
and recursive character chunking using LangChain.
"""

import re

from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.utils.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def count_tokens(text: str) -> int:
    """
    Estimate token count cheaply without loading a tokenizer.

    Args:
        text: Text to count tokens for.

    Returns:
        Approximate token count.
    """
    return len(text.split())


def remove_boilerplate(html: str) -> str:
    """
    Remove boilerplate elements (nav, footer, script, style, ads)
    from raw HTML and return cleaned text.

    Args:
        html: Raw HTML string.

    Returns:
        Cleaned text with boilerplate removed.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove non-content elements
    for tag_name in [
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "aside",
        "noscript",
        "iframe",
        "svg",
    ]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove common boilerplate class/id patterns
    boilerplate_patterns = [
        "cookie",
        "consent",
        "popup",
        "modal",
        "sidebar",
        "advertisement",
        "ad-",
        "social-share",
        "newsletter",
    ]
    for element in soup.find_all(True):
        # Guard against decomposed elements with None attrs
        if element.attrs is None:
            continue
        classes = " ".join(element.get("class", []))
        el_id = element.get("id", "") or ""
        combined = f"{classes} {el_id}".lower()
        if any(pattern in combined for pattern in boilerplate_patterns):
            element.decompose()

    text = soup.get_text(separator="\n")
    return clean_text(text)


def clean_text(text: str) -> str:
    """
    Clean raw text: normalize whitespace, remove excessive newlines.

    Args:
        text: Raw text string.

    Returns:
        Cleaned text string.
    """
    # Collapse multiple spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip lines
    lines = [line.strip() for line in text.split("\n")]
    # Remove empty lines at start/end
    text = "\n".join(lines).strip()
    return text


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_chunk: int = MIN_CHUNK_SIZE,
) -> list[str]:
    """
    Split text into chunks using LangChain's RecursiveCharacterTextSplitter.

    Uses recursive character boundaries (paragraphs, lines, sentences, words)
    and cheap word-count filtering. The embedding provider handles its own
    tokenization; this stage only keeps chunks at a practical size.

    Args:
        text: Text to chunk.
        chunk_size: Target approximate words per chunk (default 1200).
        overlap: Approximate word overlap between chunks (default 200).
        min_chunk: Minimum approximate words for a chunk to be kept (default 100).

    Returns:
        List of text chunk strings.
    """
    # Check if text is small enough to return as-is
    total_tokens = count_tokens(text)
    if total_tokens <= chunk_size:
        return [text] if total_tokens >= min_chunk else []

    try:
        # Character sizes are calibrated from approximate words to avoid
        # loading a tokenizer while still keeping chunks embedding-friendly.
        avg_chars_per_word = max(4, len(text) // max(total_tokens, 1))
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size * avg_chars_per_word,
            chunk_overlap=overlap * avg_chars_per_word,
            separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
        )

        chunks = text_splitter.split_text(text)
        filtered_chunks = [chunk for chunk in chunks if count_tokens(chunk) >= min_chunk]

        logger.info(
            "Text chunked into %d chunks (approx words: %d, filtered: %d)",
            len(filtered_chunks),
            total_tokens,
            len(chunks) - len(filtered_chunks),
        )
        return filtered_chunks
    except Exception as e:
        logger.warning(f"LangChain text splitter failed, using fallback: {e}")
        return _fallback_chunk_text(text, chunk_size, overlap, min_chunk)


def _fallback_chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_chunk: int = MIN_CHUNK_SIZE,
) -> list[str]:
    """
    Fallback word-based chunking.
    """
    words = text.split()
    total_tokens = len(words)

    if total_tokens <= chunk_size:
        return [text] if total_tokens >= min_chunk else []

    chunks = []
    start = 0
    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_words = words[start:end]
        chunk_text_str = " ".join(chunk_words)

        if len(chunk_words) >= min_chunk:
            chunks.append(chunk_text_str)

        step = max(1, chunk_size - overlap)
        start += step

    logger.info(
        "Text chunked into %d chunks (fallback, approx words: %d)",
        len(chunks),
        total_tokens,
    )
    return chunks
