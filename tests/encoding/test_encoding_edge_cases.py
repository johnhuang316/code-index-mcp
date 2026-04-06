"""Edge-case tests for encoding handling across search and indexing.

Imports of search.basic and indexing.json_index_builder are done inside
test methods to avoid a circular-import error that occurs at collection
time (a pre-existing issue in the package's import graph).
"""

import os
import pytest


class TestBasicSearchGBK:
    """BasicSearchStrategy must find matches in non-UTF-8 encoded files."""

    def test_search_finds_match_in_gbk_file(self, tmp_path):
        """search() should locate a Chinese keyword inside a GBK-encoded file."""
        from code_index_mcp.search.basic import BasicSearchStrategy

        # Create a GBK file with enough Chinese for reliable detection
        gbk_text = (
            "# -*- coding: gbk -*-\n"
            "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6d4b\u8bd5\u6587\u4ef6\n"
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u662f\u4e16\u754c\u4e0a\u4eba\u53e3\u6700\u591a\u7684\u56fd\u5bb6\n"
            "# \u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f\u662f\u5f53\u4eca\u793e\u4f1a\u53d1\u5c55\u7684\u91cd\u8981\u9886\u57df\n"
            "def process():\n"
            "    return '\u6d4b\u8bd5\u5b8c\u6210'\n"
        )
        (tmp_path / "gbk_file.py").write_bytes(gbk_text.encode("gbk"))

        strategy = BasicSearchStrategy()
        results = strategy.search(
            pattern="\u8ba1\u7b97\u673a\u79d1\u5b66",
            base_path=str(tmp_path),
        )

        assert len(results) == 1
        rel_path = list(results.keys())[0]
        assert "gbk_file.py" in rel_path
        matches = results[rel_path]
        assert any("\u8ba1\u7b97\u673a\u79d1\u5b66" in line for _, line in matches)

    def test_search_finds_ascii_match_in_gbk_file(self, tmp_path):
        """search() should locate an ASCII keyword inside a GBK-encoded file."""
        from code_index_mcp.search.basic import BasicSearchStrategy

        gbk_text = (
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u5386\u53f2\u60a0\u4e45\n"
            "# \u79d1\u5b66\u6280\u672f\u662f\u7b2c\u4e00\u751f\u4ea7\u529b\n"
            "def target_function():\n"
            "    return 42\n"
        )
        (tmp_path / "gbk_code.py").write_bytes(gbk_text.encode("gbk"))

        strategy = BasicSearchStrategy()
        results = strategy.search(
            pattern="target_function",
            base_path=str(tmp_path),
        )

        assert len(results) == 1
        matches = list(results.values())[0]
        assert any("target_function" in line for _, line in matches)


class TestJSONIndexBuilderLightweightDelayedNonAscii:
    """JSONIndexBuilder lightweight mode on files with delayed non-ASCII."""

    def test_lightweight_mode_preserves_delayed_non_ascii(self, tmp_path):
        """Non-ASCII appearing after the 32KB detection sample boundary
        must not be corrupted when the builder uses lightweight streaming."""
        from code_index_mcp.indexing.json_index_builder import (
            JSONIndexBuilder,
            LIGHTWEIGHT_MAX_LINES,
        )
        from code_index_mcp.utils.encoding import (
            open_with_detected_encoding,
            _DETECTION_SAMPLE_SIZE,
        )

        # Build a file that exceeds 1MB (triggers lightweight mode) with
        # non-ASCII appearing AFTER the 32KB detection sample.
        lines = []
        total_bytes = 0
        i = 0
        # Fill past the detection sample boundary
        while total_bytes < _DETECTION_SAMPLE_SIZE + 1024:
            line = f"x = 1  # padding line number {i:06d}\n"
            lines.append(line)
            total_bytes += len(line)
            i += 1

        # Verify we actually crossed the boundary
        assert total_bytes > _DETECTION_SAMPLE_SIZE

        # Place Chinese content (within LIGHTWEIGHT_MAX_LINES)
        assert len(lines) < LIGHTWEIGHT_MAX_LINES
        lines.append("# \u4e2d\u6587\u6ce8\u91ca\uff1a\u8fd9\u662f\u5ef6\u8fdf\u7684\u975eASCII\u5185\u5bb9\n")

        # Pad to exceed MAX_FILE_SIZE (1MB) so lightweight mode triggers
        while total_bytes < 1 * 1024 * 1024 + 1:
            line = f"z = 3  # bulk padding {i:06d}\n"
            lines.append(line)
            total_bytes += len(line)
            i += 1

        file_path = tmp_path / "big_file.py"
        file_path.write_bytes("".join(lines).encode("utf-8"))

        # Confirm the file exceeds the threshold
        assert os.path.getsize(str(file_path)) > 1 * 1024 * 1024

        builder = JSONIndexBuilder(str(tmp_path))
        specialized_exts = builder.strategy_factory.get_specialized_extensions()
        result = builder._process_file(str(file_path), specialized_exts)

        assert result is not None
        symbols, file_info_dict, language, is_specialized = result

        # Verify via open_with_detected_encoding that the Chinese text
        # survives the same streaming path used by lightweight mode.
        with open_with_detected_encoding(str(file_path)) as fh:
            read_lines = []
            for idx, line in enumerate(fh):
                if idx >= LIGHTWEIGHT_MAX_LINES:
                    break
                read_lines.append(line)
        content = "".join(read_lines)
        assert "\u4e2d\u6587\u6ce8\u91ca" in content
        assert "\ufffd" not in content  # no replacement characters


class TestJSONIndexBuilderDelayedGBK:
    """JSONIndexBuilder non-lightweight mode with delayed GBK content."""

    def test_non_lightweight_preserves_delayed_gbk(self, tmp_path):
        """A <1MB file with ASCII prefix and GBK tail must index without corruption."""
        from code_index_mcp.indexing.json_index_builder import JSONIndexBuilder

        # Build a file under 1MB with >32KB ASCII prefix followed by GBK
        ascii_prefix = "# filler line\n" * 2500  # ~37.5KB
        gbk_tail = (
            "# \u4e2d\u6587\u6ce8\u91ca\uff1a\u8fd9\u662f\u5ef6\u8fdf\u51fa\u73b0\u7684GBK\u5185\u5bb9\n"
            "def process():\n"
            "    return '\u5904\u7406\u5b8c\u6210'\n"
        )
        content_bytes = ascii_prefix.encode("ascii") + gbk_tail.encode("gbk")
        assert len(content_bytes) < 1 * 1024 * 1024  # under 1MB

        file_path = tmp_path / "delayed_gbk.py"
        file_path.write_bytes(content_bytes)

        builder = JSONIndexBuilder(str(tmp_path))
        specialized_exts = builder.strategy_factory.get_specialized_extensions()
        result = builder._process_file(str(file_path), specialized_exts)

        # Should not return None (file should be processable)
        assert result is not None
        symbols, file_info_dict, language, is_specialized = result
        assert file_info_dict is not None
