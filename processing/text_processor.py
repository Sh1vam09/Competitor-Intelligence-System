<<<<<<< HEAD
"""
Text processing module: boilerplate removal, text cleanup,
and token-based chunking.
"""

import re

import tiktoken
from bs4 import BeautifulSoup

from utils.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE
from utils.logger import get_logger

logger = get_logger(__name__)

# Tokenizer for chunk sizing
_encoder = tiktoken.get_encoding("cl100k_base")


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
    for tag_name in ["script", "style", "nav", "footer", "header",
                     "aside", "noscript", "iframe", "svg"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove common boilerplate class/id patterns
    boilerplate_patterns = [
        "cookie", "consent", "popup", "modal", "sidebar",
        "advertisement", "ad-", "social-share", "newsletter",
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


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string.

    Args:
        text: Text to count tokens for.

    Returns:
        Token count.
    """
    return len(_encoder.encode(text))


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_chunk: int = MIN_CHUNK_SIZE,
) -> list[str]:
    """
    Split text into token-based chunks with overlap.
    Each chunk targets chunk_size tokens with overlap tokens
    carried over from the previous chunk.

    Args:
        text: Text to chunk.
        chunk_size: Target tokens per chunk (default 1200).
        overlap: Token overlap between consecutive chunks (default 200).
        min_chunk: Minimum tokens for a chunk to be kept (default 100).

    Returns:
        List of text chunk strings.
    """
    tokens = _encoder.encode(text)
    total_tokens = len(tokens)

    if total_tokens <= chunk_size:
        return [text] if total_tokens >= min_chunk else []

    chunks = []
    start = 0
    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_tokens = tokens[start:end]
        chunk_text_str = _encoder.decode(chunk_tokens)

        if len(chunk_tokens) >= min_chunk:
            chunks.append(chunk_text_str)

        # Move forward by (chunk_size - overlap)
        start += chunk_size - overlap

    logger.info("Text chunked into %d chunks (total tokens: %d)", len(chunks), total_tokens)
    return chunks
=======
"""
Text processing module: boilerplate removal, text cleanup,
and token-based chunking using LangChain and HuggingFace tokenizer.
"""

import os
import re
from typing import Optional

from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_SIZE, HF_API_KEY
from utils.logger import get_logger

logger = get_logger(__name__)

# Tokenizer for chunk sizing using HuggingFace (better for Jina embeddings)
_tokenizer = None
_tokenizer_name = "bert-base-uncased"  # Default HuggingFace tokenizer


def _get_tokenizer():
    """Lazy load HuggingFace tokenizer."""
    global _tokenizer
    if _tokenizer is None:
        try:
            from transformers import AutoTokenizer

            # Set HF_TOKEN environment variable if API key is provided
            if HF_API_KEY:
                os.environ["HF_TOKEN"] = HF_API_KEY

            # Load tokenizer using transformers (compatible with LangChain)
            _tokenizer = AutoTokenizer.from_pretrained(_tokenizer_name, use_fast=True)
            logger.info(f"Loaded HuggingFace tokenizer: {_tokenizer_name}")
        except Exception as e:
            logger.warning(f"Failed to load HuggingFace tokenizer: {e}")
            # Fallback: create a simple character-based tokenizer
            logger.info("Using fallback character-based tokenizer")
            _tokenizer = None
    return _tokenizer


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string using HuggingFace tokenizer.

    Args:
        text: Text to count tokens for.

    Returns:
        Token count.
    """
    tokenizer = _get_tokenizer()
    if tokenizer is not None:
        try:
            # Use the HuggingFace tokenizer
            encoding = tokenizer.encode(text)
            return len(encoding.ids) if hasattr(encoding, "ids") else len(encoding)
        except Exception:
            pass

    # Fallback: use word-based approximation
    return len(text.split())


def _encode(text: str) -> list:
    """Encode text to tokens using tokenizer."""
    tokenizer = _get_tokenizer()
    if tokenizer is not None:
        try:
            encoding = tokenizer.encode(text)
            return encoding.ids if hasattr(encoding, "ids") else list(encoding)
        except Exception:
            pass
    # Fallback: simple word-based tokens
    return text.split()


def _decode(tokens: list) -> str:
    """Decode tokens back to text."""
    tokenizer = _get_tokenizer()
    if tokenizer is not None:
        try:
            return tokenizer.decode(tokens)
        except Exception:
            pass
    # Fallback: join with spaces
    return " ".join(tokens)


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

    Uses HuggingFace tokenizer for token counting and splits by recursive
    characters (newlines, paragraphs, etc.) for better semantic coherence.

    Args:
        text: Text to chunk.
        chunk_size: Target tokens per chunk (default 1200).
        overlap: Token overlap between consecutive chunks (default 200).
        min_chunk: Minimum tokens for a chunk to be kept (default 100).

    Returns:
        List of text chunk strings.
    """
    # Check if text is small enough to return as-is
    total_tokens = count_tokens(text)
    if total_tokens <= chunk_size:
        return [text] if total_tokens >= min_chunk else []

    try:
        # Create LangChain text splitter
        text_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
            tokenizer=_get_tokenizer(),
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )

        # Split the text
        chunks = text_splitter.split_text(text)

        # Filter out chunks that are too small
        filtered_chunks = [
            chunk for chunk in chunks if count_tokens(chunk) >= min_chunk
        ]

        logger.info(
            "Text chunked into %d chunks (total tokens: %d, filtered: %d)",
            len(filtered_chunks),
            total_tokens,
            len(chunks) - len(filtered_chunks),
        )
        return filtered_chunks
    except Exception as e:
        logger.warning(f"LangChain text splitter failed, using fallback: {e}")
        # Fallback to original token-based chunking
        return _fallback_chunk_text(text, chunk_size, overlap, min_chunk)


def _fallback_chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    min_chunk: int = MIN_CHUNK_SIZE,
) -> list[str]:
    """
    Fallback token-based chunking using HuggingFace tokenizer.
    """
    tokens = _encode(text)
    total_tokens = len(tokens)

    if total_tokens <= chunk_size:
        return [text] if total_tokens >= min_chunk else []

    chunks = []
    start = 0
    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_tokens = tokens[start:end]
        chunk_text_str = _decode(chunk_tokens)

        if len(chunk_tokens) >= min_chunk:
            chunks.append(chunk_text_str)

        # Move forward by (chunk_size - overlap)
        start += chunk_size - overlap

    logger.info(
        "Text chunked into %d chunks (fallback, total tokens: %d)",
        len(chunks),
        total_tokens,
    )
    return chunks
>>>>>>> c8b6483 (updated the report and fixed bugs)
