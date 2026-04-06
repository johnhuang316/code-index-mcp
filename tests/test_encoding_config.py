import os
import tempfile
import shutil
import unittest
from code_index_mcp.project_settings import ProjectSettings


class TestEncodingConfig(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.settings = ProjectSettings(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_default_encoding_is_none(self):
        config = self.settings.get_encoding_config()
        self.assertIsNone(config["default_encoding"])

    def test_update_default_encoding(self):
        self.settings.update_encoding_config({"default_encoding": "gbk"})
        config = self.settings.get_encoding_config()
        self.assertEqual(config["default_encoding"], "gbk")

    def test_round_trip_persistence(self):
        self.settings.update_encoding_config({"default_encoding": "shift_jis"})
        fresh = ProjectSettings(self.tmp_dir)
        config = fresh.get_encoding_config()
        self.assertEqual(config["default_encoding"], "shift_jis")

    def test_clear_encoding(self):
        self.settings.update_encoding_config({"default_encoding": "gbk"})
        self.settings.update_encoding_config({"default_encoding": None})
        config = self.settings.get_encoding_config()
        self.assertIsNone(config["default_encoding"])


if __name__ == "__main__":
    unittest.main()
