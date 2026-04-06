"""Tests for encoding detection and file reading utility."""

import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from code_index_mcp.utils.encoding import detect_encoding, read_file_content, open_with_detected_encoding


class TestDetectEncoding(unittest.TestCase):
    """Tests for the detect_encoding() function."""

    def test_detect_utf8(self):
        raw = "Hello, world!".encode("utf-8")
        enc = detect_encoding(raw)
        self.assertEqual(enc, "utf-8")  # ASCII is always normalised to utf-8

    def test_detect_utf8_with_bom(self):
        raw = b"\xef\xbb\xbf" + "Hello".encode("utf-8")
        enc = detect_encoding(raw)
        self.assertIn("utf", enc.lower())

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
        self.assertIsInstance(enc, str)
        # Verify the detected encoding can actually decode the bytes
        decoded = raw.decode(enc)
        self.assertGreater(len(decoded), 0)

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
        self.assertIsInstance(enc, str)
        decoded = raw.decode(enc)
        self.assertGreater(len(decoded), 0)

    def test_detect_shift_jis(self):
        # Japanese text encoded as Shift-JIS
        text = "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c"
        raw = text.encode("shift_jis")
        enc = detect_encoding(raw)
        self.assertIn(enc.lower(), ("shift_jis", "shift-jis", "cp932", "euc-jp"))

    def test_detect_empty_bytes(self):
        enc = detect_encoding(b"")
        self.assertEqual(enc, "utf-8")

    def test_detect_pure_ascii(self):
        raw = b"def foo():\n    return 42\n"
        enc = detect_encoding(raw)
        self.assertEqual(enc, "utf-8")

    def test_detect_encoding_logs_confidence(self):
        """Confidence score should be logged at DEBUG level."""
        with self.assertLogs("code_index_mcp.utils.encoding", level=logging.DEBUG) as cm:
            detect_encoding("Hello, world!".encode("utf-8"))
        self.assertTrue(any("confidence" in msg.lower() for msg in cm.output))


class TestReadFileContent(unittest.TestCase):
    """Tests for the read_file_content() function."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_read_utf8_file(self):
        f = os.path.join(self.tmp_dir, "test.py")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("def hello():\n    return 'world'\n")
        content = read_file_content(f)
        self.assertIn("def hello():", content)
        self.assertIn("return 'world'", content)

    def test_read_gbk_file(self):
        f = os.path.join(self.tmp_dir, "test_gbk.py")
        text = (
            "# -*- coding: gbk -*-\n"
            "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684Python\u6587\u4ef6\n"
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u662f\u4e16\u754c\u4e0a\u4eba\u53e3\u6700\u591a\u7684\u56fd\u5bb6\n"
            "# \u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f\u662f\u5f53\u4eca\u793e\u4f1a\u53d1\u5c55\u7684\u91cd\u8981\u9886\u57df\n"
            "def main():\n"
            "    print('\u6d4b\u8bd5\u8f6f\u4ef6\u5de5\u7a0b')\n"
            "    print('\u6570\u636e\u5e93\u7ba1\u7406\u7cfb\u7edf')\n"
        )
        with open(f, "wb") as fh:
            fh.write(text.encode("gbk"))
        content = read_file_content(f)
        self.assertIn("\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd", content)
        self.assertIn("def main():", content)
        self.assertIn("\u6d4b\u8bd5", content)

    def test_read_gb2312_file(self):
        f = os.path.join(self.tmp_dir, "test_gb2312.txt")
        text = (
            "\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u5386\u53f2\u60a0\u4e45\u3002\n"
            "\u79d1\u5b66\u6280\u672f\u662f\u7b2c\u4e00\u751f\u4ea7\u529b\u3002\n"
            "\u6559\u80b2\u662f\u56fd\u5bb6\u53d1\u5c55\u7684\u57fa\u7840\u3002\n"
            "\u6587\u5316\u662f\u6c11\u65cf\u7684\u7cbe\u795e\u5bb6\u56ed\u3002\n"
        )
        with open(f, "wb") as fh:
            fh.write(text.encode("gb2312"))
        content = read_file_content(f)
        self.assertIn("\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd", content)
        self.assertIn("\u79d1\u5b66\u6280\u672f", content)

    def test_read_shift_jis_file(self):
        f = os.path.join(self.tmp_dir, "test_sjis.txt")
        text = "\u3053\u3093\u306b\u3061\u306f\u4e16\u754c\n"
        with open(f, "wb") as fh:
            fh.write(text.encode("shift_jis"))
        content = read_file_content(f)
        self.assertIn("\u3053\u3093\u306b\u3061\u306f", content)

    def test_read_binary_file_raises(self):
        f = os.path.join(self.tmp_dir, "binary.bin")
        with open(f, "wb") as fh:
            fh.write(b"\x00\x01\x02\x03binary content")
        with self.assertRaises(ValueError):
            read_file_content(f)

    def test_read_nonexistent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_file_content("/nonexistent/path/file.txt")

    def test_read_with_max_lines(self):
        f = os.path.join(self.tmp_dir, "multiline.txt")
        lines = [f"line {i}" for i in range(100)]
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        content = read_file_content(f, max_lines=5)
        self.assertLessEqual(content.count("\n"), 5)
        self.assertIn("line 0", content)
        self.assertNotIn("line 99", content)

    def test_read_utf8_sig_file(self):
        f = os.path.join(self.tmp_dir, "bom.txt")
        with open(f, "wb") as fh:
            fh.write(b"\xef\xbb\xbfHello BOM")
        content = read_file_content(f)
        self.assertIn("Hello BOM", content)

    def test_read_latin1_file(self):
        f = os.path.join(self.tmp_dir, "latin.txt")
        text = "caf\u00e9 r\u00e9sum\u00e9"
        with open(f, "wb") as fh:
            fh.write(text.encode("latin-1"))
        content = read_file_content(f)
        self.assertIn("caf", content)
        self.assertIn("sum", content)

    def test_read_large_gbk_file(self):
        """Ensure encoding detection works for files larger than the sample size."""
        f = os.path.join(self.tmp_dir, "large_gbk.py")
        # Create a large GBK file: repeated Chinese text + code
        line = "# \u8fd9\u662f\u4e00\u884c\u4e2d\u6587\u6ce8\u91ca\uff0c\u7528\u4e8e\u6d4b\u8bd5\u5927\u6587\u4ef6\u7f16\u7801\u68c0\u6d4b\n"
        text = line * 2000  # ~60KB of GBK text
        with open(f, "wb") as fh:
            fh.write(text.encode("gbk"))
        content = read_file_content(f)
        self.assertIn("\u4e2d\u6587\u6ce8\u91ca", content)


class TestDelayedNonAscii(unittest.TestCase):
    """Tests for files whose first 32KB are ASCII but later content is not."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_read_file_with_non_ascii_after_32kb(self):
        """Content beyond the 32KB detection sample must not be corrupted."""
        f = os.path.join(self.tmp_dir, "delayed.py")
        # Build a file: >32KB of pure ASCII, then UTF-8 Chinese text
        ascii_prefix = "# filler line\n" * 2500  # ~37.5 KB of ASCII
        self.assertGreater(len(ascii_prefix.encode("ascii")), 32 * 1024)
        utf8_tail = "# \u4e2d\u6587\u6ce8\u91ca\uff1a\u8fd9\u662f\u5ef6\u8fdf\u51fa\u73b0\u7684\u975e ASCII \u5185\u5bb9\n"
        with open(f, "wb") as fh:
            fh.write(ascii_prefix.encode("ascii") + utf8_tail.encode("utf-8"))

        content = read_file_content(f)
        self.assertIn("\u4e2d\u6587\u6ce8\u91ca", content)
        self.assertNotIn("\ufffd", content)  # no replacement characters

    def test_open_with_detected_encoding_non_ascii_after_32kb(self):
        """Streaming path uses sample-only detection; delayed UTF-8
        beyond the 32KB sample still works because the default is UTF-8."""
        f = os.path.join(self.tmp_dir, "delayed_stream.py")
        ascii_prefix = "# padding\n" * 3500  # ~38.5 KB
        self.assertGreater(len(ascii_prefix.encode("ascii")), 32 * 1024)
        utf8_tail = "# \u8fd9\u662f\u5ef6\u8fdf\u7684\u975eASCII\u5185\u5bb9\n"
        with open(f, "wb") as fh:
            fh.write(ascii_prefix.encode("ascii") + utf8_tail.encode("utf-8"))

        with open_with_detected_encoding(f) as fh:
            lines = fh.readlines()
        combined = "".join(lines)
        self.assertIn("\u5ef6\u8fdf", combined)
        self.assertNotIn("\ufffd", combined)

    def test_read_file_with_gbk_after_32kb_ascii(self):
        """GBK content beyond the 32KB detection sample must be decoded correctly."""
        f = os.path.join(self.tmp_dir, "delayed_gbk.py")
        ascii_prefix = "# filler line\n" * 2500
        self.assertGreater(len(ascii_prefix.encode("ascii")), 32 * 1024)
        gbk_tail = "# \u4e2d\u6587\u6ce8\u91ca\uff1a\u8fd9\u662f\u5ef6\u8fdf\u51fa\u73b0\u7684GBK\u5185\u5bb9\n"
        with open(f, "wb") as fh:
            fh.write(ascii_prefix.encode("ascii") + gbk_tail.encode("gbk"))

        content = read_file_content(f)
        self.assertIn("\u4e2d\u6587\u6ce8\u91ca", content)
        self.assertNotIn("\ufffd", content)

    def test_read_file_with_shift_jis_after_32kb_ascii(self):
        """Shift-JIS content beyond the 32KB detection sample must be decoded correctly."""
        f = os.path.join(self.tmp_dir, "delayed_sjis.txt")
        ascii_prefix = "# filler line\n" * 2500
        self.assertGreater(len(ascii_prefix.encode("ascii")), 32 * 1024)
        sjis_tail = "# \u3053\u308c\u306f\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8\u3067\u3059\n"
        with open(f, "wb") as fh:
            fh.write(ascii_prefix.encode("ascii") + sjis_tail.encode("shift_jis"))

        content = read_file_content(f)
        self.assertIn("\u65e5\u672c\u8a9e", content)
        self.assertNotIn("\ufffd", content)

    def test_open_with_detected_encoding_gbk_after_32kb_ascii(self):
        """Streaming path: GBK after 32KB ASCII is decoded as UTF-8 with
        replacement.  This is an accepted tradeoff -- read_file_content
        handles this case correctly for non-streaming consumers."""
        f = os.path.join(self.tmp_dir, "delayed_gbk_stream.py")
        ascii_prefix = "# filler line\n" * 2500
        self.assertGreater(len(ascii_prefix.encode("ascii")), 32 * 1024)
        gbk_tail = "# \u4e2d\u6587\u6ce8\u91ca\uff1a\u8fd9\u662f\u5ef6\u8fdf\u51fa\u73b0\u7684GBK\u5185\u5bb9\n"
        with open(f, "wb") as fh:
            fh.write(ascii_prefix.encode("ascii") + gbk_tail.encode("gbk"))

        with open_with_detected_encoding(f) as fh:
            lines = fh.readlines()
        combined = "".join(lines)
        # The ASCII prefix must survive intact
        self.assertIn("# filler line", combined)


class TestOpenWithDetectedEncoding(unittest.TestCase):
    """Tests for open_with_detected_encoding()."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_reads_utf8_file_line_by_line(self):
        f = os.path.join(self.tmp_dir, "utf8.py")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("line1\nline2\nline3\n")
        with open_with_detected_encoding(f) as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0].strip(), "line1")

    def test_reads_gbk_file_line_by_line(self):
        f = os.path.join(self.tmp_dir, "gbk.py")
        text = (
            "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6d4b\u8bd5\u6587\u4ef6\n"
            "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\u662f\u4e16\u754c\u4e0a\u4eba\u53e3\u6700\u591a\u7684\u56fd\u5bb6\n"
            "# \u8ba1\u7b97\u673a\u79d1\u5b66\u4e0e\u6280\u672f\u662f\u5f53\u4eca\u793e\u4f1a\u53d1\u5c55\u7684\u91cd\u8981\u9886\u57df\n"
        )
        with open(f, "wb") as fh:
            fh.write(text.encode("gbk"))
        with open_with_detected_encoding(f) as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 3)
        combined = "".join(lines)
        self.assertIn("GBK", combined)

    def test_binary_file_raises_valueerror(self):
        f = os.path.join(self.tmp_dir, "binary.bin")
        with open(f, "wb") as fh:
            fh.write(b"\x00\x01\x02\x03binary")
        with self.assertRaises(ValueError):
            with open_with_detected_encoding(f) as fh:
                pass

    def test_nonexistent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            with open_with_detected_encoding("/nonexistent/file.txt") as fh:
                pass

    def test_returns_iterable_context_manager(self):
        f = os.path.join(self.tmp_dir, "ctx.txt")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("hello\n")
        with open_with_detected_encoding(f) as fh:
            self.assertTrue(hasattr(fh, 'readline'))
            self.assertTrue(hasattr(fh, '__iter__'))


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
        with self.assertRaises(ValueError):
            with open_with_detected_encoding(path, encoding="utf-8") as fh:
                pass


if __name__ == "__main__":
    unittest.main()
