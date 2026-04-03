import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from code_index_mcp.project_settings import ProjectSettings


def test_migrates_from_old_location(tmp_path):
    """Patterns in file_watcher should be migrated to project level on load."""
    settings = ProjectSettings(str(tmp_path))

    # Write config with old location
    config_path = settings.get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    old_config = {"file_watcher": {"additional_exclude_patterns": ["old_pattern/"]}}
    with open(config_path, 'w') as f:
        json.dump(old_config, f)

    # Load should migrate
    loaded = settings.load_config()
    assert loaded.get("additional_exclude_patterns") == ["old_pattern/"]
    # Old location should be cleaned up
    assert "additional_exclude_patterns" not in loaded.get("file_watcher", {})


def test_no_migration_if_new_location_exists(tmp_path):
    """Don't overwrite new location with old values."""
    settings = ProjectSettings(str(tmp_path))

    config_path = settings.get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    config = {
        "additional_exclude_patterns": ["new_pattern/"],
        "file_watcher": {"additional_exclude_patterns": ["old_pattern/"]}
    }
    with open(config_path, 'w') as f:
        json.dump(config, f)

    loaded = settings.load_config()
    assert loaded.get("additional_exclude_patterns") == ["new_pattern/"]


def test_update_exclude_patterns(tmp_path):
    """update_exclude_patterns should save to project level."""
    settings = ProjectSettings(str(tmp_path))

    config_path = settings.get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump({}, f)

    settings.update_exclude_patterns(["logs/", "*.tmp"])

    loaded = settings.load_config()
    assert loaded.get("additional_exclude_patterns") == ["logs/", "*.tmp"]
