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


def read_file_content(
    file_path: str,
    max_lines: Optional[int] = None,
    encoding: str | None = None,
) -> str:
    """
    Read a file with automatic encoding detection.

    Reads the file as raw bytes, detects the encoding, and decodes.
    Binary files (containing NUL bytes in the first 8 KB) raise ValueError.

    Args:
        file_path: Absolute path to the file to read.
        max_lines: If set, return only the first N lines.
        encoding: If provided, use this encoding directly instead of
            auto-detecting.  Errors with an explicit encoding are raised
            (no silent fallback).

    Returns:
        Decoded file content as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file appears to be binary.
        LookupError: If an explicit encoding name is invalid.
        UnicodeDecodeError: If an explicit encoding cannot decode the file.
        OSError: On I/O errors.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        raw = f.read()

    # Check for binary content (NUL byte in first 8 KB)
    if b"\x00" in raw[:8192]:
        raise ValueError(f"File appears to be binary: {file_path}")

    # Explicit encoding: decode directly, fail loudly on errors
    if encoding is not None:
        content = raw.decode(encoding)  # raises LookupError / UnicodeDecodeError

        if max_lines is not None:
            lines = content.split("\n", max_lines)
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines])
        return content

    # Auto-detect encoding from a sample
    sample = raw[:_DETECTION_SAMPLE_SIZE]
    detected = detect_encoding(sample)

    # Decode with the detected encoding
    try:
        content = raw.decode(detected)
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
                    detected,
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
                detected,
            )
            content = raw.decode("utf-8", errors="replace")

    if max_lines is not None:
        lines = content.split("\n", max_lines)
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines])

    return content


@contextmanager
def open_with_detected_encoding(
    file_path: str,
    encoding: str | None = None,
) -> Iterator[IO[str]]:
    """
    Open a file with automatically detected encoding for streaming reads.

    When *encoding* is provided, the file is opened directly with that
    encoding (no sample read or detection).  Otherwise, reads a 32 KB
    sample to detect the encoding via charset-normalizer.

    For files with delayed non-UTF-8 content beyond 32 KB, pass encoding
    explicitly.

    Args:
        file_path: Absolute path to the file.
        encoding: If provided, use this encoding directly instead of
            auto-detecting.

    Yields:
        A text-mode file object using the detected (or explicit) encoding
        with ``errors='replace'``.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file appears to be binary.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if encoding is not None:
        # Explicit encoding: skip sample read / detection entirely
        fh = open(file_path, "r", encoding=encoding, errors="replace")
        try:
            yield fh
        finally:
            fh.close()
        return

    # Read a 32 KB sample for binary check + encoding detection
    with open(file_path, "rb") as f:
        sample = f.read(_DETECTION_SAMPLE_SIZE)

    if b"\x00" in sample[:8192]:
        raise ValueError(f"File appears to be binary: {file_path}")

    detected = detect_encoding(sample)

    fh = open(file_path, "r", encoding=detected, errors="replace")
    try:
        yield fh
    finally:
        fh.close()
