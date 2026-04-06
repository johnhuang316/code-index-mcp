# PR #93 Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 code review issues found in PR #93 to improve code quality and correctness of the custom-extensions feature.

**Architecture:** Extract a shared `normalize_extension()` utility to eliminate 3x duplicated normalization logic. Move duplicated service methods (`_get_extra_extensions`, `_get_exclude_patterns`) to `BaseService`. Fix parameter passing to avoid fragile instance variable stashing. Thread extra_extensions through to file watcher's FileFilter.

**Tech Stack:** Python 3.12+, pytest

---

### Task 1: Extract `normalize_extension` utility

**Files:**
- Create: `src/code_index_mcp/utils/extensions.py`
- Modify: `src/code_index_mcp/utils/__init__.py`
- Modify: `src/code_index_mcp/project_settings.py` (update_extra_extensions, get_extra_extensions)
- Modify: `src/code_index_mcp/utils/file_filter.py` (FileFilter.__init__)
- Modify: `src/code_index_mcp/server.py` (CLI parsing)

- [ ] Create `normalize_extension(ext: str) -> str` in `utils/extensions.py`
- [ ] Export from `utils/__init__.py`
- [ ] Replace inline normalization in `project_settings.py` `update_extra_extensions` and `get_extra_extensions`
- [ ] Replace inline normalization in `file_filter.py` `FileFilter.__init__` - just call `normalize_extension` on each ext
- [ ] In `server.py` CLI parsing (lines 524-527), normalize each extension using `normalize_extension`

### Task 2: Remove fragile `_extra_extensions` instance variable

**Files:**
- Modify: `src/code_index_mcp/services/project_management_service.py`

- [ ] Change `_execute_initialization_workflow(self, path)` signature to accept `extra_extensions: list[str] | None = None`
- [ ] Remove `self._extra_extensions = extra_extensions` from `initialize_project()`
- [ ] Pass `extra_extensions` as argument to `_execute_initialization_workflow(path, extra_extensions)`
- [ ] Replace `getattr(self, '_extra_extensions', None)` with the parameter

### Task 3: Move duplicated `_get_extra_extensions` and `_get_exclude_patterns` to BaseService

**Files:**
- Modify: `src/code_index_mcp/services/base_service.py`
- Modify: `src/code_index_mcp/services/project_management_service.py`
- Modify: `src/code_index_mcp/services/index_management_service.py`

- [ ] Add `_get_extra_extensions` and `_get_exclude_patterns` to `BaseService`
- [ ] Remove both methods from `ProjectManagementService`
- [ ] Remove both methods from `IndexManagementService`

### Task 4: Pass extra_extensions to file watcher's FileFilter

**Files:**
- Modify: `src/code_index_mcp/services/file_watcher_service.py`

- [ ] Add `extra_extensions` parameter to `DebounceEventHandler.__init__`
- [ ] Pass `extra_extensions` to `FileFilter(additional_excludes, extra_extensions=extra_extensions)`
- [ ] Update `_create_event_handler` to read extra_extensions from settings and pass through
- [ ] Update `restart_observer` similarly

### Task 5: Run all tests, commit

- [ ] Run full test suite
- [ ] Commit all changes
