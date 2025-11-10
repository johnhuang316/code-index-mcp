# MCP Restart Playbook (November 10, 2025)

This runbook is for the first LLM/agent session *after* the MCP server restarts (for example, after bumping dependencies or recycling the FastMCP process). Follow every step in order so we quickly regain context, validate the upgraded toolchain, and communicate status to the rest of the team.

---

## 1. Current Snapshot
- **Branch**: `mcp-upgrade-notes`
- **Python**: 3.13.2 (uv-managed)
- **Key dependency**: `mcp>=1.21.0,<2.0.0` (synced across `pyproject.toml`, `requirements.txt`, and `uv.lock`)
- **Latest validation**: `uv run pytest` — 16 tests passed on **November 10, 2025 @ 02:05 UTC**
- **Reference doc**: `docs/mcp-upgrade-notes.md` (rationale, API deltas, validation checklist)

If any of these details drift (new branch, newer SDK, etc.) update this file before handing off.

---

## 2. Post-Restart MCP Calls (must run all tools)
Run through every exposed MCP primitive to guarantee parity after restart. Use the table below as a checklist and record each response summary.

| # | Tool | Minimum Input | Expected outcome |
|---|------|---------------|------------------|
| 1 | `set_project_path` | `path="C:\Users\p10362321\project\code-index-mcp"` | Indexed ~149 files; watcher initialized. |
| 2 | `build_deep_index` | - | Project re-indexed. Found ~149 files / ~1,070 symbols. |
| 3 | `search_code_advanced` | `pattern="FastMCP", file_pattern="src/**/*.py", max_results=20` | Hits in `server.py` plus pagination metadata. |
| 4 | `find_files` | `pattern="tests/**/*.py"` | Returns 10 test modules. |
| 5 | `get_file_summary` | `file_path="src/code_index_mcp/server.py"` | ~390 lines, 20+ functions reported. |
| 6 | `refresh_index` | - | Shallow index re-built with ~149 files. |
| 7 | `get_settings_info` | - | Shows temp/settings dirs, writable=true. |
| 8 | `create_temp_directory` | - | Confirms directory exists/created. |
| 9 | `check_temp_directory` | - | Lists `index.db`, `index.msgpack`, `index.shallow.json`. |
|10 | `clear_settings` | - | Project settings, index, and cache have been cleared (rerun #1 + #2). |
|11 | `refresh_search_tools` | - | Available: ['ripgrep', 'basic']; preferred: ripgrep. |
|12 | `get_file_watcher_status` | - | status: active, debounce_seconds=6. |
|13 | `configure_file_watcher` | `enabled=True, debounce_seconds=6` | Confirmation message (restart may be required). |

Notes:
- After running `clear_settings`, immediately repeat `set_project_path` + `build_deep_index` to restore context before proceeding.
- If any tool fails, stop the playbook, capture output, and escalate before continuing.

Log each response summary in the session notes so the next engineer knows everything is green.

---

## 3. CLI / End-to-End Smoke
Run these in the repo root once the MCP tools succeed:

```powershell
uv run code-index-mcp --project-path C:\Users\p10362321\project\code-index-mcp
uv run pytest
```

- Treat any warning or stderr output as a blocker.
- Capture timestamps + durations; attach to release prep if we are close to tagging.

---

## 4. Communicate Status
When handing the session back to the team, summarize:

- **SDK state**: Confirm we are still on MCP 1.21.0 (with context injection + capability helpers).
- **Tool cache**: Mention that clients should re-cache tool lists after restart (FastMCP now enforces metadata changes).
- **Known issues**: Note any skipped steps, flaky tests, or manual interventions.
- **Next action**: “Ready for release prep” or “Need follow-up on X” — whichever applies after the smoke tests.

---

## 5. Troubleshooting Quick Reference
- **`set_project_path` fails** → Ensure the repo path is accessible (sandbox permissions) and no other agent locked `index.db`. Run `clear_settings()` then retry.
- **Search returns zero results** → Run `refresh_search_tools()`; if ripgrep missing, fall back to `basic` and flag the infra team.
- **Watcher inactive** → Call `configure_file_watcher(enabled=True)` and `refresh_index()`. Document if it remains inactive.
- **CLI smoke exits non-zero** → Capture full stdout/stderr, file an issue linked to `docs/mcp-upgrade-notes.md`, and pause release work.

Keep this section updated with any new gotchas discovered during restarts.

---

## 6. Hand-off Checklist
- [ ] Steps 1–4 executed and logged in the current session.
- [ ] Any deviations documented (include timestamps + command output).
- [ ] This playbook reviewed/updated if procedures changed.

If all boxes are checked, the MCP server is considered healthy and ready for normal development or release activities.
