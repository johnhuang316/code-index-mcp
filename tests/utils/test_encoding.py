"""Tests for encoding detection and file reading utility."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import pytest

from code_index_mcp.utils.encoding import detect_encoding, read_file_content, open_with_detected_encoding


class TestDetectEncoding:
    """Tests for the detect_encoding() function."""

    def test_detect_utf8(self):
        raw = "Hello, world!".encode("utf-8")
        enc = detect_encoding(raw)
        assert enc == "utf-8"  # ASCII is always normalised to utf-8

    def test_detect_utf8_with_bom(self):
        raw = b"\xef\xbb\xbf" + "Hello".encode("utf-8")
        enc = detect_encoding(raw)
        assert "utf" in enc.lower()

    def test_detect_gbk(self):
        # Longer Chinese text for reliable GBK detection
        text = (
            "\u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6d4b\u8bd5\u6587\u4ef6\u3002\n"
            "\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u662f\u4e16\u754c\u4e0a\u4eba\u53e3\u6700\u591a\u7684\u56fd\u5bb6\u3002\n"
            "\u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f\u662f\u5f53\u4eca\u793e\u4f1a\u53d1\u5c55\u7684\u91cd\u8981\u9886\u57df\u3002\n"
            "\u8f6f\u4ef6\u5de5\u7a0b\u662f\u4e00\u95e8\u7814\u7a76\u5982\u4f55\u7cfb\u7edf\u5316\u5730\u5f00\u53d1\u548c\u7ef4\u62a4\u8f6f\u4ef6\u7684\u5b66\u79d1\u3002\n"
        )
        raw = text.encode("gbk")
        enc = detect_encoding(raw)
        # charset-normalizer should detect a GB-family or compatible CJK encoding
        # The key test is that read_file_content correctly decodes GBK files
        # (see TestReadFileContent). Here we just verify detection doesn't crash
        # and returns something decodable.
        assert isinstance(enc, str)
        # Verify the detected encoding can actually decode the bytes
        decoded = raw.decode(enc)
        assert len(decoded) > 0

    def test_detect_gb2312(self):
        # Longer Chinese text that fits in GB2312 for reliable detection
        text = (
            "\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u5386\u53f2\u60a0\u4e45\u3002\n"
            "\u79d1\u5b66\u6280\u672f\u662f\u7b2c\u4e00\u751f\u4ea7\u529b\u3002\n"
            "\u6559\u80b2\u662f\u56fd\u5bb6\u53d1\u5c55\u7684\u57fa\u7840\u3002\n"
            "\u6587\u5316\u662f\u6c11\u65cf\u7684\u7cbe\u795e\u5bb6\u56ed\u3002\n"
        )
        raw = text.encode("gb2312")
        enc = detect_encoding(raw)
        assert isinstance(enc, str)
        decoded = raw.decode(enc)
        assert len(decoded) > 0

    def test_detect_shift_jis(self):
        # Japanese text encoded as Shift-JIS
        text = "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c"
        raw = text.encode("shift_jis")
        enc = detect_encoding(raw)
        assert enc.lower() in ("shift_jis", "shift-jis", "cp932", "euc-jp")

    def test_detect_empty_bytes(self):
        enc = detect_encoding(b"")
        assert enc == "utf-8"

    def test_detect_pure_ascii(self):
        raw = b"def foo():\n    return 42\n"
        enc = detect_encoding(raw)
        # ASCII is always normalised to UTF-8 to avoid corruption when
        # the sample is pure ASCII but the full file contains non-ASCII.
        assert enc == "utf-8"

    def test_detect_encoding_logs_confidence(self, caplog):
        """Confidence score should be logged at DEBUG level."""
        import logging
        with caplog.at_level(logging.DEBUG, logger="code_index_mcp.utils.encoding"):
            detect_encoding("Hello, world!".encode("utf-8"))
        assert any("confidence" in record.message.lower() for record in caplog.records)


class TestReadFileContent:
    """Tests for the read_file_content() function."""

    def test_read_utf8_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
        content = read_file_content(str(f))
        assert "def hello():" in content
        assert "return 'world'" in content

    def test_read_gbk_file(self, tmp_path):
        f = tmp_path / "test_gbk.py"
        text = (
            "# -*- coding: gbk -*-\n"
            "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684Python\u6587\u4ef6\n"
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u662f\u4e16\u754c\u4e0a\u4eba\u53e3\u6700\u591a\u7684\u56fd\u5bb6\n"
            "# \u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f\u662f\u5f53\u4eca\u793e\u4f1a\u53d1\u5c55\u7684\u91cd\u8981\u9886\u57df\n"
            "def main():\n"
            "    print('\u6d4b\u8bd5\u8f6f\u4ef6\u5de5\u7a0b')\n"
            "    print('\u6570\u636e\u5e93\u7ba1\u7406\u7cfb\u7edf')\n"
        )
        f.write_bytes(text.encode("gbk"))
        content = read_file_content(str(f))
        assert "\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd" in content
        assert "def main():" in content
        assert "\u6d4b\u8bd5" in content

    def test_read_gb2312_file(self, tmp_path):
        f = tmp_path / "test_gb2312.txt"
        text = (
            "\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u5386\u53f2\u60a0\u4e45\u3002\n"
            "\u79d1\u5b66\u6280\u672f\u662f\u7b2c\u4e00\u751f\u4ea7\u529b\u3002\n"
            "\u6559\u80b2\u662f\u56fd\u5bb6\u53d1\u5c55\u7684\u57fa\u7840\u3002\n"
            "\u6587\u5316\u662f\u6c11\u65cf\u7684\u7cbe\u795e\u5bb6\u56ed\u3002\n"
        )
        f.write_bytes(text.encode("gb2312"))
        content = read_file_content(str(f))
        assert "\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd" in content
        assert "\u79d1\u5b66\u6280\u672f" in content

    def test_read_shift_jis_file(self, tmp_path):
        f = tmp_path / "test_sjis.txt"
        text = "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c\n"
        f.write_bytes(text.encode("shift_jis"))
        content = read_file_content(str(f))
        assert "\u3053\u3093\u306b\u3061\u306f" in content

    def test_read_binary_file_raises(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02\x03binary content")
        with pytest.raises(ValueError, match="binary"):
            read_file_content(str(f))

    def test_read_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            read_file_content("/nonexistent/path/file.txt")

    def test_read_with_max_lines(self, tmp_path):
        f = tmp_path / "multiline.txt"
        lines = [f"line {i}" for i in range(100)]
        f.write_text("\n".join(lines), encoding="utf-8")
        content = read_file_content(str(f), max_lines=5)
        assert content.count("\n") <= 5
        assert "line 0" in content
        assert "line 99" not in content

    def test_read_utf8_sig_file(self, tmp_path):
        f = tmp_path / "bom.txt"
        f.write_bytes(b"\xef\xbb\xbfHello BOM")
        content = read_file_content(str(f))
        assert "Hello BOM" in content

    def test_read_latin1_file(self, tmp_path):
        f = tmp_path / "latin.txt"
        text = "caf\u00e9 r\u00e9sum\u00e9"
        f.write_bytes(text.encode("latin-1"))
        content = read_file_content(str(f))
        assert "caf" in content
        assert "sum" in content

    def test_read_large_gbk_file(self, tmp_path):
        """Ensure encoding detection works for files larger than the sample size."""
        f = tmp_path / "large_gbk.py"
        # Create a large GBK file: repeated Chinese text + code
        line = "# \u8fd9\u662f\u4e00\u884c\u4e2d\u6587\u6ce8\u91ca\uff0c\u7528\u4e8e\u6d4b\u8bd5\u5927\u6587\u4ef6\u7f16\u7801\u68c0\u6d4b\n"
        text = line * 2000  # ~60KB of GBK text
        f.write_bytes(text.encode("gbk"))
        content = read_file_content(str(f))
        assert "\u4e2d\u6587\u6ce8\u91ca" in content


class TestDelayedNonAscii:
    """Tests for files whose first 32KB are ASCII but later content is not."""

    def test_read_file_with_non_ascii_after_32kb(self, tmp_path):
        """Content beyond the 32KB detection sample must not be corrupted."""
        f = tmp_path / "delayed.py"
        # Build a file: >32KB of pure ASCII, then UTF-8 Chinese text
        ascii_prefix = "# filler line\n" * 2500  # ~37.5 KB of ASCII
        assert len(ascii_prefix.encode("ascii")) > 32 * 1024
        utf8_tail = "# \u4e2d\u6587\u6ce8\u91ca\uff1a\u8fd9\u662f\u5ef6\u8fdf\u51fa\u73b0\u7684\u975e ASCII \u5185\u5bb9\n"
        f.write_bytes(ascii_prefix.encode("ascii") + utf8_tail.encode("utf-8"))

        content = read_file_content(str(f))
        # The Chinese characters must survive round-trip without replacement
        assert "\u4e2d\u6587\u6ce8\u91ca" in content
        assert "\ufffd" not in content  # no replacement characters

    def test_open_with_detected_encoding_non_ascii_after_32kb(self, tmp_path):
        """Streaming path uses sample-only detection; delayed UTF-8
        beyond the 32KB sample still works because the default is UTF-8."""
        f = tmp_path / "delayed_stream.py"
        ascii_prefix = "# padding\n" * 3500  # ~38.5 KB
        assert len(ascii_prefix.encode("ascii")) > 32 * 1024
        utf8_tail = "# \u8fd9\u662f\u5ef6\u8fdf\u7684\u975eASCII\u5185\u5bb9\n"
        f.write_bytes(ascii_prefix.encode("ascii") + utf8_tail.encode("utf-8"))

        with open_with_detected_encoding(str(f)) as fh:
            lines = fh.readlines()
        combined = "".join(lines)
        # UTF-8 tail decoded correctly because sample detected as UTF-8
        assert "\u5ef6\u8fdf" in combined
        assert "\ufffd" not in combined

    def test_read_file_with_gbk_after_32kb_ascii(self, tmp_path):
        """GBK content beyond the 32KB detection sample must be decoded correctly."""
        f = tmp_path / "delayed_gbk.py"
        # 2500 lines of "# filler line\n" = ~37.5KB of pure ASCII
        ascii_prefix = "# filler line\n" * 2500
        assert len(ascii_prefix.encode("ascii")) > 32 * 1024
        gbk_tail = "# \u4e2d\u6587\u6ce8\u91ca\uff1a\u8fd9\u662f\u5ef6\u8fdf\u51fa\u73b0\u7684GBK\u5185\u5bb9\n"
        f.write_bytes(ascii_prefix.encode("ascii") + gbk_tail.encode("gbk"))

        content = read_file_content(str(f))
        assert "\u4e2d\u6587\u6ce8\u91ca" in content
        assert "\ufffd" not in content  # no replacement characters

    def test_read_file_with_shift_jis_after_32kb_ascii(self, tmp_path):
        """Shift-JIS content beyond the 32KB detection sample must be decoded correctly."""
        f = tmp_path / "delayed_sjis.txt"
        ascii_prefix = "# filler line\n" * 2500
        assert len(ascii_prefix.encode("ascii")) > 32 * 1024
        sjis_tail = "# \u3053\u308c\u306f\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8\u3067\u3059\n"
        f.write_bytes(ascii_prefix.encode("ascii") + sjis_tail.encode("shift_jis"))

        content = read_file_content(str(f))
        assert "\u65e5\u672c\u8a9e" in content
        assert "\ufffd" not in content

    def test_open_with_detected_encoding_gbk_after_32kb_ascii(self, tmp_path):
        """Streaming path: GBK after 32KB ASCII is decoded as UTF-8 with
        replacement.  This is an accepted tradeoff -- read_file_content
        handles this case correctly for non-streaming consumers."""
        f = tmp_path / "delayed_gbk_stream.py"
        ascii_prefix = "# filler line\n" * 2500
        assert len(ascii_prefix.encode("ascii")) > 32 * 1024
        gbk_tail = "# \u4e2d\u6587\u6ce8\u91ca\uff1a\u8fd9\u662f\u5ef6\u8fdf\u51fa\u73b0\u7684GBK\u5185\u5bb9\n"
        f.write_bytes(ascii_prefix.encode("ascii") + gbk_tail.encode("gbk"))

        with open_with_detected_encoding(str(f)) as fh:
            lines = fh.readlines()
        combined = "".join(lines)
        # The ASCII prefix must survive intact
        assert "# filler line" in combined
        # GBK bytes decoded as UTF-8 will produce replacement chars --
        # this is the documented tradeoff for streaming performance.
        # The non-streaming read_file_content handles this correctly.


class TestOpenWithDetectedEncoding:
    """Tests for open_with_detected_encoding()."""

    def test_reads_utf8_file_line_by_line(self, tmp_path):
        f = tmp_path / "utf8.py"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        with open_with_detected_encoding(str(f)) as fh:
            lines = fh.readlines()
        assert len(lines) == 3
        assert lines[0].strip() == "line1"

    def test_reads_gbk_file_line_by_line(self, tmp_path):
        f = tmp_path / "gbk.py"
        # Use longer Chinese text for reliable GBK detection
        text = (
            "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6d4b\u8bd5\u6587\u4ef6\n"
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u662f\u4e16\u754c\u4e0a\u4eba\u53e3\u6700\u591a\u7684\u56fd\u5bb6\n"
            "# \u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f\u662f\u5f53\u4eca\u793e\u4f1a\u53d1\u5c55\u7684\u91cd\u8981\u9886\u57df\n"
        )
        f.write_bytes(text.encode("gbk"))
        with open_with_detected_encoding(str(f)) as fh:
            lines = fh.readlines()
        assert len(lines) == 3
        # Verify the content is decodable (encoding detected correctly)
        combined = "".join(lines)
        assert "GBK" in combined

    def test_binary_file_raises_valueerror(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02\x03binary")
        with pytest.raises(ValueError, match="binary"):
            with open_with_detected_encoding(str(f)) as fh:
                pass

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            with open_with_detected_encoding("/nonexistent/file.txt") as fh:
                pass

    def test_returns_iterable_context_manager(self, tmp_path):
        f = tmp_path / "ctx.txt"
        f.write_text("hello\n", encoding="utf-8")
        with open_with_detected_encoding(str(f)) as fh:
            assert hasattr(fh, 'readline')
            assert hasattr(fh, '__iter__')


class TestReadFileContentEncodingOverride(unittest.TestCase):
    """Tests for the explicit encoding parameter on read_file_content()."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_explicit_gbk_encoding_decodes_correctly(self):
        """When encoding='gbk' is passed, GBK bytes are decoded correctly."""
        text = "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6d4b\u8bd5\u6587\u4ef6\n"
        path = os.path.join(self.tmp_dir, "gbk_explicit.py")
        with open(path, "wb") as f:
            f.write(text.encode("gbk"))
        content = read_file_content(path, encoding="gbk")
        self.assertIn("\u4f7f\u7528GBK", content)
        self.assertIn("\u6d4b\u8bd5\u6587\u4ef6", content)

    def test_explicit_encoding_skips_detection(self):
        """When an explicit encoding is provided, charset-normalizer must not be called."""
        path = os.path.join(self.tmp_dir, "skip_detect.txt")
        with open(path, "wb") as f:
            f.write(b"hello world\n")
        with patch("code_index_mcp.utils.encoding.from_bytes") as mock_from_bytes:
            content = read_file_content(path, encoding="utf-8")
        mock_from_bytes.assert_not_called()
        self.assertIn("hello", content)

    def test_invalid_encoding_raises_lookup_error(self):
        """An invalid encoding name must raise LookupError, not silently fallback."""
        path = os.path.join(self.tmp_dir, "invalid_enc.txt")
        with open(path, "wb") as f:
            f.write(b"some bytes\n")
        with self.assertRaises(LookupError):
            read_file_content(path, encoding="not-a-real-encoding")


class TestOpenWithDetectedEncodingOverride(unittest.TestCase):
    """Tests for the explicit encoding parameter on open_with_detected_encoding()."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_explicit_encoding_used_for_streaming(self):
        """When encoding='gbk' is passed, the file is opened with GBK."""
        text = "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6d4b\u8bd5\u6587\u4ef6\n"
        path = os.path.join(self.tmp_dir, "gbk_stream.py")
        with open(path, "wb") as f:
            f.write(text.encode("gbk"))
        with open_with_detected_encoding(path, encoding="gbk") as fh:
            content = fh.read()
        self.assertIn("\u4f7f\u7528GBK", content)
        self.assertIn("\u6d4b\u8bd5\u6587\u4ef6", content)

    def test_explicit_encoding_skips_detection_streaming(self):
        """When an explicit encoding is provided, charset-normalizer must not be called."""
        path = os.path.join(self.tmp_dir, "skip_detect_stream.txt")
        with open(path, "wb") as f:
            f.write(b"hello world\n")
        with patch("code_index_mcp.utils.encoding.from_bytes") as mock_from_bytes:
            with open_with_detected_encoding(path, encoding="utf-8") as fh:
                content = fh.read()
        mock_from_bytes.assert_not_called()
        self.assertIn("hello", content)

    def test_explicit_encoding_rejects_binary(self):
        """Binary files must be rejected even when an explicit encoding is given."""
        path = os.path.join(self.tmp_dir, "binary_explicit.bin")
        with open(path, "wb") as f:
            f.write(b"\x00\x01\x02\x03binary content")
        with self.assertRaises(ValueError, msg="binary"):
            with open_with_detected_encoding(path, encoding="utf-8") as fh:
                pass
