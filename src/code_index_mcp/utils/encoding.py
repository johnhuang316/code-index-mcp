"""
Encoding detection and file reading utility.

Provides automatic encoding detection for non-UTF-8 files (GBK, GB2312,
Shift-JIS, etc.) using the charset-normalizer library. This module is the
single point of entry for reading user project files across the codebase.

Usage:
    from code_index_mcp.utils.encoding import read_file_content, detect_encoding

    content = read_file_content("/path/to/file.py")
    encoding = detect_encoding(raw_bytes)
"""

import logging
import os
from typing import Optional

from charset_normalizer import from_bytes

logger = logging.getLogger(__name__)

# Sample size for encoding detection (32 KB is enough for reliable detection)
_DETECTION_SAMPLE_SIZE = 32 * 1024


def detect_encoding(raw_bytes: bytes) -> str:
    """
    Detect the encoding of raw bytes using charset-normalizer.

    Args:
        raw_bytes: Raw bytes to detect encoding for.

    Returns:
        Detected encoding name (e.g. 'utf-8', 'gb2312', 'gbk', 'shift_jis').
        Falls back to 'utf-8' if detection fails or confidence is too low.
    """
    if not raw_bytes:
        return "utf-8"

    result = from_bytes(raw_bytes)
    best = result.best()

    if best is not None and best.encoding:
        detected = best.encoding.lower()
        logger.debug("Detected encoding: %s", detected)
        return detected

    logger.debug("Could not detect encoding, falling back to utf-8")
    return "utf-8"


def read_file_content(file_path: str, max_lines: Optional[int] = None) -> str:
    """
    Read a file with automatic encoding detection.

    Reads the file as raw bytes, detects the encoding, and decodes.
    Binary files (containing NUL bytes in the first 8 KB) raise ValueError.

    Args:
        file_path: Absolute path to the file to read.
        max_lines: If set, return only the first N lines.

    Returns:
        Decoded file content as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file appears to be binary.
        OSError: On I/O errors.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        raw = f.read()

    # Check for binary content (NUL byte in first 8 KB)
    if b"\x00" in raw[:8192]:
        raise ValueError(f"File appears to be binary: {file_path}")

    # Detect encoding from a sample
    sample = raw[:_DETECTION_SAMPLE_SIZE]
    encoding = detect_encoding(sample)

    # Decode with the detected encoding, falling back to utf-8 with replacement
    try:
        content = raw.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        logger.warning(
            "Failed to decode %s with detected encoding %s, "
            "falling back to utf-8 with replacement",
            file_path,
            encoding,
        )
        content = raw.decode("utf-8", errors="replace")

    if max_lines is not None:
        lines = content.split("\n", max_lines)
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines])

    return content
