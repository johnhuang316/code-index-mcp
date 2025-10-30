"""Tests for pagination validation helper."""
from pathlib import Path as _TestPath
import sys

ROOT = _TestPath(__file__).resolve().parents[2]
SRC_PATH = ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from code_index_mcp.utils.validation import ValidationHelper


def test_validate_pagination_accepts_valid_values():
    assert ValidationHelper.validate_pagination(0, None) is None
    assert ValidationHelper.validate_pagination(5, 10) is None


def test_validate_pagination_rejects_invalid_values():
    assert ValidationHelper.validate_pagination(-1, None) == "start_index cannot be negative"
    assert ValidationHelper.validate_pagination(0, 0) == "max_results must be greater than zero when provided"
    assert ValidationHelper.validate_pagination(0, "a") == "max_results must be an integer when provided"
    assert ValidationHelper.validate_pagination("a", None) == "start_index must be an integer"
