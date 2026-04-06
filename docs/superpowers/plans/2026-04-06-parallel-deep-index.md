# Parallel Deep Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make deep indexing faster for large codebases by exposing existing parallel processing configuration and improving timeout handling.

**Architecture:** The codebase already uses ThreadPoolExecutor for parallel file processing in both JSONIndexBuilder and SQLiteIndexBuilder. This plan adds: (1) a configurable `max_workers` parameter on the `build_deep_index` MCP tool, (2) a persistent indexing config in ProjectSettings, (3) a dynamic timeout that scales with file count instead of a fixed 30s, and (4) tests for the new configuration paths.

**Tech Stack:** Python 3, concurrent.futures.ThreadPoolExecutor, SQLite, pytest

---

### Task 1: Add indexing configuration to ProjectSettings

**Files:**
- Modify: `src/code_index_mcp/project_settings.py`

- [ ] **Step 1: Add `get_indexing_config` and `update_indexing_config` methods**

Add methods following the same pattern as `get_file_watcher_config` / `update_file_watcher_config`.

- [ ] **Step 2: Write test for indexing config round-trip**

- [ ] **Step 3: Commit**

### Task 2: Make build timeout dynamic in SQLiteIndexBuilder

**Files:**
- Modify: `src/code_index_mcp/indexing/sqlite_index_builder.py`

- [ ] **Step 1: Replace fixed PARALLEL_BUILD_TIMEOUT_SECONDS with a function that scales by file count**

Use formula: `max(30, file_count * 0.5)` seconds, capped at 600s.

- [ ] **Step 2: Accept `timeout` parameter in `build_index`**

- [ ] **Step 3: Write test for dynamic timeout**

- [ ] **Step 4: Commit**

### Task 3: Thread max_workers through the service layer

**Files:**
- Modify: `src/code_index_mcp/services/index_management_service.py`
- Modify: `src/code_index_mcp/indexing/sqlite_index_manager.py`
- Modify: `src/code_index_mcp/indexing/deep_index_manager.py`

- [ ] **Step 1: Add `max_workers` parameter to `build_index` in SQLiteIndexManager, DeepIndexManager, and IndexManagementService.rebuild_deep_index**

- [ ] **Step 2: Read default max_workers from settings when not explicitly provided**

- [ ] **Step 3: Write test**

- [ ] **Step 4: Commit**

### Task 4: Expose max_workers on the build_deep_index MCP tool

**Files:**
- Modify: `src/code_index_mcp/server.py`

- [ ] **Step 1: Add `max_workers` parameter to `build_deep_index` tool function**

- [ ] **Step 2: Commit**

### Task 5: Write concurrency safety and integration tests

**Files:**
- Create: `tests/indexing/test_parallel_deep_index.py`

- [ ] **Step 1: Test max_workers propagation through the stack**
- [ ] **Step 2: Test dynamic timeout calculation**
- [ ] **Step 3: Test settings-based configuration**
- [ ] **Step 4: Commit**
