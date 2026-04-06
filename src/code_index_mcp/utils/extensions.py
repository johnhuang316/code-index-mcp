"""
Extension normalization utilities for the Code Index MCP server.

Provides a single source of truth for normalizing file extensions
(lowercase, dot-prefixed, stripped) used across the codebase.
"""


def normalize_extension(ext: str) -> str:
    """Normalize a file extension to lowercase with a leading dot.

    Strips whitespace, lowercases, and ensures a leading dot.
    Returns an empty string for blank / whitespace-only input.

    Examples:
        >>> normalize_extension("  .RSC ")
        '.rsc'
        >>> normalize_extension("conf")
        '.conf'
        >>> normalize_extension("")
        ''
    """
    ext = ext.strip().lower()
    if not ext:
        return ""
    if not ext.startswith("."):
        ext = "." + ext
    return ext
