import io
import os
import shutil
import tempfile
import unittest


class TestReadFileWithEncoding(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def _write(self, name, content_bytes):
        path = os.path.join(self.tmp_dir, name)
        with open(path, "wb") as f:
            f.write(content_bytes)
        return path

    def test_utf8_default(self):
        from code_index_mcp.utils.encoding import read_file_with_encoding
        path = self._write("test.py", "def hello(): pass\n".encode("utf-8"))
        content = read_file_with_encoding(path)
        self.assertIn("def hello", content)

    def test_gbk_with_explicit_encoding(self):
        from code_index_mcp.utils.encoding import read_file_with_encoding
        text = "# \u8fd9\u662f\u4e00\u4e2a\u4f7f\u7528GBK\u7f16\u7801\u7684\u6587\u4ef6\ndef \u8ba1\u7b97(): pass\n"
        path = self._write("test.py", text.encode("gbk"))
        content = read_file_with_encoding(path, encoding="gbk")
        self.assertIn("\u8fd9\u662f\u4e00\u4e2a", content)
        self.assertIn("\u8ba1\u7b97", content)

    def test_shift_jis_with_explicit_encoding(self):
        from code_index_mcp.utils.encoding import read_file_with_encoding
        text = "# \u3053\u3093\u306b\u3061\u306f\u4e16\u754c\n"
        path = self._write("test.txt", text.encode("shift_jis"))
        content = read_file_with_encoding(path, encoding="shift_jis")
        self.assertIn("\u3053\u3093\u306b\u3061\u306f", content)

    def test_none_encoding_uses_utf8(self):
        from code_index_mcp.utils.encoding import read_file_with_encoding
        path = self._write("test.py", "hello\n".encode("utf-8"))
        content = read_file_with_encoding(path, encoding=None)
        self.assertEqual(content.strip(), "hello")

    def test_binary_file_raises(self):
        from code_index_mcp.utils.encoding import read_file_with_encoding
        path = self._write("bin.dat", b"\x00\x01\x02\x03binary")
        with self.assertRaises(ValueError):
            read_file_with_encoding(path)

    def test_nonexistent_file_raises(self):
        from code_index_mcp.utils.encoding import read_file_with_encoding
        with self.assertRaises(FileNotFoundError):
            read_file_with_encoding("/no/such/file.py")

    def test_invalid_encoding_raises(self):
        from code_index_mcp.utils.encoding import read_file_with_encoding
        path = self._write("test.py", b"hello")
        with self.assertRaises(LookupError):
            read_file_with_encoding(path, encoding="not-a-real-encoding")

    def test_max_lines(self):
        from code_index_mcp.utils.encoding import read_file_with_encoding
        lines = "\n".join(f"line {i}" for i in range(100))
        path = self._write("test.txt", lines.encode("utf-8"))
        content = read_file_with_encoding(path, max_lines=5)
        self.assertIn("line 0", content)
        self.assertNotIn("line 99", content)


class TestOpenFileWithEncoding(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def _write(self, name, content_bytes):
        path = os.path.join(self.tmp_dir, name)
        with open(path, "wb") as f:
            f.write(content_bytes)
        return path

    def test_streaming_utf8_default(self):
        from code_index_mcp.utils.encoding import open_file_with_encoding
        path = self._write("test.py", "line1\nline2\n".encode("utf-8"))
        with open_file_with_encoding(path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)

    def test_streaming_gbk(self):
        from code_index_mcp.utils.encoding import open_file_with_encoding
        text = "# \u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd\ndef main(): pass\n"
        path = self._write("test.py", text.encode("gbk"))
        with open_file_with_encoding(path, encoding="gbk") as f:
            content = f.read()
        self.assertIn("\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd", content)

    def test_streaming_binary_raises(self):
        from code_index_mcp.utils.encoding import open_file_with_encoding
        path = self._write("bin.dat", b"\x00\x01binary")
        with self.assertRaises(ValueError):
            with open_file_with_encoding(path) as f:
                f.read()


class TestEncodingConfig(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_default_encoding_is_none(self):
        from code_index_mcp.project_settings import ProjectSettings
        settings = ProjectSettings(self.tmp_dir)
        config = settings.get_encoding_config()
        self.assertIsNone(config["default_encoding"])

    def test_update_and_read_encoding(self):
        from code_index_mcp.project_settings import ProjectSettings
        settings = ProjectSettings(self.tmp_dir)
        settings.update_encoding_config({"default_encoding": "gbk"})
        config = settings.get_encoding_config()
        self.assertEqual(config["default_encoding"], "gbk")

    def test_round_trip_persistence(self):
        from code_index_mcp.project_settings import ProjectSettings
        settings = ProjectSettings(self.tmp_dir)
        settings.update_encoding_config({"default_encoding": "shift_jis"})
        fresh = ProjectSettings(self.tmp_dir)
        self.assertEqual(fresh.get_encoding_config()["default_encoding"], "shift_jis")

    def test_clear_encoding(self):
        from code_index_mcp.project_settings import ProjectSettings
        settings = ProjectSettings(self.tmp_dir)
        settings.update_encoding_config({"default_encoding": "gbk"})
        settings.update_encoding_config({"default_encoding": None})
        self.assertIsNone(settings.get_encoding_config()["default_encoding"])


class TestBasicSearchWithEncoding(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_search_finds_gbk_content(self):
        from code_index_mcp.search.basic import BasicSearchStrategy
        text = "# \u8fd9\u662fGBK\u6587\u4ef6\ndef \u8ba1\u7b97(): pass\n"
        path = os.path.join(self.tmp_dir, "test.py")
        with open(path, "wb") as f:
            f.write(text.encode("gbk"))
        strategy = BasicSearchStrategy()
        results = strategy.search("\u8ba1\u7b97", self.tmp_dir, encoding="gbk")
        self.assertTrue(len(results) > 0)


class TestGBKProjectEndToEnd(unittest.TestCase):
    """Prove a GBK project works end-to-end with default_encoding."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_gbk_file_indexed_and_searchable(self):
        from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager
        from code_index_mcp.search.basic import BasicSearchStrategy

        text = "# 这是GBK编码\ndef 计算总和(numbers):\n    return sum(numbers)\n"
        path = os.path.join(self.tmp_dir, "main.py")
        with open(path, "wb") as f:
            f.write(text.encode("gbk"))

        mgr = SQLiteIndexManager()
        mgr.set_project_path(self.tmp_dir, encoding="gbk")
        mgr.build_index()
        stats = mgr.get_index_stats()
        self.assertEqual(stats["indexed_files"], 1)

        strategy = BasicSearchStrategy()
        results = strategy.search("计算", self.tmp_dir, encoding="gbk")
        self.assertTrue(len(results) > 0)

    def test_encoding_config_persists_and_is_used(self):
        from code_index_mcp.project_settings import ProjectSettings
        from code_index_mcp.utils.encoding import read_file_with_encoding

        settings = ProjectSettings(self.tmp_dir)
        settings.update_encoding_config({"default_encoding": "gbk"})

        text = "# 中华人民共和国\n"
        path = os.path.join(self.tmp_dir, "test.py")
        with open(path, "wb") as f:
            f.write(text.encode("gbk"))

        enc = settings.get_encoding_config()["default_encoding"]
        content = read_file_with_encoding(path, encoding=enc)
        self.assertIn("中华人民共和国", content)


if __name__ == "__main__":
    unittest.main()
