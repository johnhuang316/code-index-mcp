"""
File encoding utility.

Provides explicit-encoding file reading. No auto-detection — when encoding
is not specified, UTF-8 is used. Projects using non-UTF-8 encodings should
set default_encoding via set_project_path().
"""

import logging
import os
from contextlib import contextmanager
from typing import IO, Iterator, Optional

logger = logging.getLogger(__name__)


def read_file_with_encoding(
    file_path: str,
    encoding: Optional[str] = None,
    max_lines: Optional[int] = None,
) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    enc = encoding or "utf-8"
    with open(file_path, "rb") as f:
        raw = f.read()
    if b"\x00" in raw[:8192]:
        raise ValueError(f"File appears to be binary: {file_path}")
    content = raw.decode(enc)
    if max_lines is not None:
        lines = content.split("\n", max_lines)
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines])
    return content


@contextmanager
def open_file_with_encoding(
    file_path: str,
    encoding: Optional[str] = None,
) -> Iterator[IO[str]]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    enc = encoding or "utf-8"
    with open(file_path, "rb") as f:
        sample = f.read(8192)
    if b"\x00" in sample:
        raise ValueError(f"File appears to be binary: {file_path}")
    fh = open(file_path, "r", encoding=enc, errors="replace")
    try:
        yield fh
    finally:
        fh.close()
