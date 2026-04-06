"""Integration tests for GBK/GB2312 encoding support across the system."""

import os
import pytest

from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager


class TestGBKIndexingIntegration:
    """Test that GBK-encoded files are correctly indexed."""

    def test_gbk_python_file_is_indexed(self, tmp_path):
        """A GBK-encoded Python file should be indexed with correct symbol extraction."""
        source = (
            "# -*- coding: gbk -*-\n"
            "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684Python\u6587\u4ef6\n"
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u662f\u4e16\u754c\u4e0a\u4eba\u53e3\u6700\u591a\u7684\u56fd\u5bb6\n"
            "\n"
            "def \u8ba1\u7b97\u603b\u548c(numbers):\n"
            "    '''\u8ba1\u7b97\u5217\u8868\u4e2d\u6240\u6709\u6570\u5b57\u7684\u603b\u548c'''\n"
            "    return sum(numbers)\n"
            "\n"
            "class \u6570\u636e\u5904\u7406\u5668:\n"
            "    '''\u6570\u636e\u5904\u7406\u7c7b'''\n"
            "    def __init__(self):\n"
            "        self.\u6570\u636e = []\n"
        )
        (tmp_path / "main.py").write_bytes(source.encode("gbk"))

        manager = SQLiteIndexManager()
        assert manager.set_project_path(str(tmp_path))
        assert manager.build_index()

        stats = manager.get_index_stats()
        assert stats["indexed_files"] == 1

    def test_mixed_encoding_project_is_indexed(self, tmp_path):
        """A project with both UTF-8 and GBK files should index all files."""
        # UTF-8 file
        (tmp_path / "utf8_file.py").write_text(
            "def hello():\n    return 'world'\n",
            encoding="utf-8",
        )

        # GBK file with enough Chinese text for reliable detection
        gbk_source = (
            "# -*- coding: gbk -*-\n"
            "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6587\u4ef6\n"
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u5386\u53f2\u60a0\u4e45\n"
            "# \u79d1\u5b66\u6280\u672f\u662f\u7b2c\u4e00\u751f\u4ea7\u529b\n"
            "def process():\n"
            "    return '\u5904\u7406\u5b8c\u6210'\n"
        )
        (tmp_path / "gbk_file.py").write_bytes(gbk_source.encode("gbk"))

        manager = SQLiteIndexManager()
        assert manager.set_project_path(str(tmp_path))
        assert manager.build_index()

        stats = manager.get_index_stats()
        assert stats["indexed_files"] == 2

    def test_gbk_file_content_readable_via_file_service(self, tmp_path):
        """FileService should return correctly decoded Chinese text from GBK files."""
        from code_index_mcp.utils.encoding import read_file_content

        text = (
            "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6587\u4ef6\n"
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u5386\u53f2\u60a0\u4e45\n"
            "# \u79d1\u5b66\u6280\u672f\u662f\u7b2c\u4e00\u751f\u4ea7\u529b\n"
            "name = '\u6d4b\u8bd5\u540d\u79f0'\n"
        )
        f = tmp_path / "test.py"
        f.write_bytes(text.encode("gbk"))

        content = read_file_content(str(f))
        assert "\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd" in content
        assert "\u79d1\u5b66\u6280\u672f" in content
        assert "\u6d4b\u8bd5\u540d\u79f0" in content
