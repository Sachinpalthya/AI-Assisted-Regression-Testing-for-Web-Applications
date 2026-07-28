"""
sample_project/string_utils.py

String utility functions for common text processing operations.
"""

import re
from typing import Optional


def reverse_string(s: str) -> str:
    """
    Return the reverse of the input string.

    Args:
        s: Input string

    Returns:
        Reversed string

    Raises:
        TypeError: If input is not a string
    """
    if not isinstance(s, str):
        raise TypeError(f"Expected str, got {type(s).__name__}")
    return s[::-1]


def count_words(text: str) -> int:
    """
    Count the number of words in a string.
    Words are sequences of non-whitespace characters.

    Args:
        text: Input text

    Returns:
        Word count (0 for empty/whitespace-only strings)
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    return len(text.split())


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate a string to max_length characters, appending a suffix if truncated.

    Args:
        text:       Input string
        max_length: Maximum allowed length (including suffix)
        suffix:     String appended when truncation occurs (default: "...")

    Returns:
        Original string if within limit, otherwise truncated string with suffix.

    Raises:
        ValueError: If max_length is less than len(suffix)
    """
    if max_length < len(suffix):
        raise ValueError(f"max_length ({max_length}) must be >= len(suffix) ({len(suffix)})")
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def is_palindrome(s: str) -> bool:
    """
    Check whether a string is a palindrome (ignores case and spaces).

    Args:
        s: Input string

    Returns:
        True if the string reads the same forwards and backwards
    """
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", s).lower()
    return cleaned == cleaned[::-1]


def slug(text: str) -> str:
    """
    Convert a string to a URL-friendly slug.
    Lowercases, strips special chars, replaces spaces with hyphens.

    Args:
        text: Human-readable title or phrase

    Returns:
        URL slug, e.g. "Hello World!" → "hello-world"
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def extract_emails(text: str) -> list[str]:
    """
    Extract all valid email addresses from a block of text.

    Args:
        text: Input text that may contain email addresses

    Returns:
        List of extracted email strings (may be empty)
    """
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    return re.findall(pattern, text)


def title_case(text: str) -> str:
    """
    Convert a string to title case, handling common exceptions
    (articles, prepositions) that should remain lowercase unless first word.

    Args:
        text: Input string

    Returns:
        Title-cased string
    """
    EXCEPTIONS = {"a", "an", "the", "and", "but", "or", "for", "nor",
                  "on", "at", "to", "by", "in", "of", "up", "as"}
    words = text.lower().split()
    result = []
    for i, word in enumerate(words):
        if i == 0 or word not in EXCEPTIONS:
            result.append(word.capitalize())
        else:
            result.append(word)
    return " ".join(result)
