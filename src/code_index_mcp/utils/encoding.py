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
from contextlib import contextmanager
from typing import IO, Iterator, Optional

from charset_normalizer import from_bytes

logger = logging.getLogger(__name__)

# Sample size for encoding detection (32 KB is enough for reliable detection)
_DETECTION_SAMPLE_SIZE = 32 * 1024


def _is_pure_ascii(data: bytes) -> bool:
    """Check if all bytes in data are ASCII (< 128)."""
    try:
        data.decode("ascii")
        return True
    except UnicodeDecodeError:
        return False


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
        confidence = best.coherence  # float 0.0-1.0 from charset-normalizer
        logger.debug(
            "Detected encoding: %s (confidence: %.2f)", detected, confidence
        )
        # Normalize ASCII to UTF-8: when only a 32KB sample is analysed the
        # detector may return "ascii" even though bytes beyond the sample
        # contain non-ASCII content.  Since ASCII is a strict subset of
        # UTF-8, promoting to UTF-8 is always safe and avoids silent
        # corruption via errors='replace' on the tail of the file.
        if detected == "ascii":
            return "utf-8"
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

    # Decode with the detected encoding
    try:
        content = raw.decode(encoding)
    except (UnicodeDecodeError, LookupError) as first_err:
        # Two-pass: if the sample was pure ASCII and decode failed, the real
        # encoding lives in the bytes beyond the sample.  Re-detect from the
        # failure region and retry.
        content = None
        if isinstance(first_err, UnicodeDecodeError) and _is_pure_ascii(sample):
            # Re-detect from the failure point onward so the non-ASCII
            # bytes dominate the sample (including preceding ASCII would
            # dilute the signal and cause mis-detection).
            region = raw[first_err.start:]
            re_encoding = detect_encoding(region)
            if re_encoding != "utf-8":
                logger.debug(
                    "Two-pass re-detection for %s: %s -> %s",
                    file_path,
                    encoding,
                    re_encoding,
                )
                try:
                    content = raw.decode(re_encoding)
                except (UnicodeDecodeError, LookupError):
                    pass

        if content is None:
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


@contextmanager
def open_with_detected_encoding(file_path: str) -> Iterator[IO[str]]:
    """
    Open a file with automatically detected encoding for streaming reads.

    Reads a 32 KB sample to detect encoding, checks for binary content,
    then returns a text-mode file object opened with the detected encoding
    and ``errors='replace'``.  The caller can iterate line-by-line without
    loading the whole file into memory.

    Design note -- streaming vs full detection
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Unlike :func:`read_file_content` (which performs two-pass detection and
    can handle non-UTF-8 bytes that appear *after* the 32 KB sample), this
    function detects encoding from the first 32 KB **only**.  If the sample
    is pure ASCII the file is opened as UTF-8 (a superset of ASCII).

    This means files whose first 32 KB are ASCII but whose later content
    uses a different codec (e.g. GBK) will have the later bytes decoded
    with replacement characters.  This is an intentional performance
    tradeoff: scanning the entire file to locate the first non-ASCII byte
    would negate the benefit of streaming.  In practice such files are
    extremely rare, and consumers that need full correctness should use
    :func:`read_file_content` instead.

    Args:
        file_path: Absolute path to the file.

    Yields:
        A text-mode file object using the detected encoding.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file appears to be binary.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read a sample for binary check + encoding detection
    with open(file_path, "rb") as f:
        sample = f.read(_DETECTION_SAMPLE_SIZE)

    if b"\x00" in sample[:8192]:
        raise ValueError(f"File appears to be binary: {file_path}")

    encoding = detect_encoding(sample)

    fh = open(file_path, "r", encoding=encoding, errors="replace")
    try:
        yield fh
    finally:
        fh.close()
