"""End-to-end bootstrap test for custom extensions via CLI.

Proves that the full path works:
  main() -> _CLI_CONFIG -> indexer_lifespan() -> initialize_project(extra_extensions=...)
actually delivers extra_extensions through the real startup flow — not just in
isolated unit-level pieces.
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, call

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from code_index_mcp.project_settings import ProjectSettings


def _run_lifespan_via_main(argv: list[str]):
    """Call ``main(argv)`` but replace ``mcp.run`` with a helper that
    actually enters the ``indexer_lifespan`` async context manager.

    This exercises the real bootstrap chain:
      main() -> _CLI_CONFIG -> mcp.run (intercepted) -> indexer_lifespan
      -> ProjectManagementService.initialize_project(extra_extensions=...)

    Only ``mcp.run`` is mocked (to avoid starting a real stdio server).
    Everything else — CLI parsing, _CLI_CONFIG, lifespan, settings
    persistence, service logic — is real.

    Returns the CodeIndexerContext yielded by the lifespan so the caller
    can inspect settings, file counts, etc.
    """
    from code_index_mcp.server import indexer_lifespan, mcp as mcp_server, main

    captured = {}

    def fake_mcp_run(**_kwargs):
        """Instead of starting a real transport, enter and exit the lifespan."""
        async def _enter_lifespan():
            async with indexer_lifespan(mcp_server) as ctx:
                captured["context"] = ctx

        asyncio.run(_enter_lifespan())

    with patch("code_index_mcp.server.mcp.run", side_effect=fake_mcp_run):
        main(argv)

    return captured.get("context")


class TestBootstrapExtraExtensionsEndToEnd(unittest.TestCase):
    """End-to-end: main() -> lifespan -> initialize_project -> settings.

    This test proves that calling main() with --extra-extensions flows
    through the full bootstrap path (CLI parsing -> _CLI_CONFIG ->
    indexer_lifespan -> ProjectManagementService.initialize_project)
    and correctly persists or clears extra_extensions in real
    ProjectSettings — not just in isolated unit-level pieces.
    """

    def setUp(self):
        # Isolated temp project directory with sample files
        self.project_dir = tempfile.mkdtemp(prefix="cimcp_proj_")
        with open(os.path.join(self.project_dir, "main.py"), "w") as f:
            f.write("print('hello')\n")
        with open(os.path.join(self.project_dir, "router.rsc"), "w") as f:
            f.write("/ip address add\n")

        # Isolated index root so tests don't pollute system /tmp
        self.index_root = tempfile.mkdtemp(prefix="cimcp_idx_")
        self._orig_custom_root = getattr(ProjectSettings, "custom_index_root", None)
        ProjectSettings.custom_index_root = self.index_root

    def tearDown(self):
        ProjectSettings.custom_index_root = self._orig_custom_root
        shutil.rmtree(self.project_dir, ignore_errors=True)
        shutil.rmtree(self.index_root, ignore_errors=True)

    # ------------------------------------------------------------------

    def test_bootstrap_set_then_clear_extra_extensions(self):
        """Full bootstrap: set extensions via CLI, then clear with empty string.

        Phase 1: ``--extra-extensions .rsc`` -> lifespan calls
                 initialize_project(path, extra_extensions=[".rsc"]).
                 ProjectSettings.update_extra_extensions([".rsc"]) persists
                 the extension to the config file on disk.

        Phase 2: ``--extra-extensions ''`` -> lifespan calls
                 initialize_project(path, extra_extensions=[]).
                 ProjectSettings.update_extra_extensions([]) clears the
                 previously persisted extensions.

        We verify both the in-memory _CLI_CONFIG state AND the on-disk
        config written by the real ProjectSettings through the full
        bootstrap chain.
        """
        from code_index_mcp.server import _CLI_CONFIG

        # Phase 1 — set extensions via full bootstrap path
        ctx1 = _run_lifespan_via_main([
            "--project-path", self.project_dir,
            "--extra-extensions", ".rsc",
        ])

        # _CLI_CONFIG should reflect parsed CLI args
        self.assertEqual(
            _CLI_CONFIG.extra_extensions, [".rsc"],
            "_CLI_CONFIG.extra_extensions should be ['.rsc'] after "
            "main(['--extra-extensions', '.rsc'])",
        )

        # The lifespan created a real ProjectSettings and called
        # update_extra_extensions on it. Verify the config file on disk
        # was written with the extension.
        config_path = os.path.join(ctx1.settings.settings_path, "config.json")
        self.assertTrue(
            os.path.exists(config_path),
            f"Config file should exist at {config_path} after bootstrap",
        )
        with open(config_path, encoding="utf-8") as f:
            config_phase1 = json.load(f)
        self.assertIn(
            ".rsc", config_phase1.get("extra_extensions", []),
            "Phase 1 failed: .rsc should be persisted in the config file "
            "after bootstrap with --extra-extensions .rsc",
        )

        # Phase 2 — clear extensions with explicit empty string
        ctx2 = _run_lifespan_via_main([
            "--project-path", self.project_dir,
            "--extra-extensions", "",
        ])

        # _CLI_CONFIG should reflect the explicit empty parse
        self.assertEqual(
            _CLI_CONFIG.extra_extensions, [],
            "_CLI_CONFIG.extra_extensions should be [] after "
            "main(['--extra-extensions', ''])",
        )

        # The config file written by update_extra_extensions([]) should
        # now contain an empty list, proving the clearing path works
        # end-to-end.
        config_path2 = os.path.join(ctx2.settings.settings_path, "config.json")
        with open(config_path2, encoding="utf-8") as f:
            config_phase2 = json.load(f)
        self.assertEqual(
            config_phase2.get("extra_extensions", ["NOT_CLEARED"]), [],
            "Phase 2 failed: extra_extensions should be [] in the config "
            "file after bootstrap with --extra-extensions ''",
        )


if __name__ == "__main__":
    unittest.main()
