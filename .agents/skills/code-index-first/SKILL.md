---
name: code-index-first
description: Use when exploring, searching, or reading code in a repository indexed by code-index-mcp, instead of reaching for the agent's own file tools or shell equivalents (glob, grep, ripgrep, find, ls, cat, head, wc). Covers session setup, choosing between search_code_advanced, find_files, get_file_summary, and get_symbol_body, and answering "what does this project do" without reading whole files.
---

# Code Index First

The code-index MCP server exposes indexed, symbol-aware file tools. When it is connected,
file discovery, code search, and code reading should go through it rather than the agent's
built-in file tools or shell commands.

The deep index extracts function signatures, class definitions, imports, and call
relationships from every source file. Searches return structural information rather than
plain text matches, and a single function can be read without loading the file around it.

## Tool names

This skill uses the tool names as the server defines them: `set_project_path`,
`build_deep_index`, `refresh_index`, `find_files`, `search_code_advanced`,
`get_file_summary`, `get_symbol_body`, `configure_file_watcher`.

Some agents namespace MCP tools. If the bare name is not callable, look for the same tool
under the server's prefix — for example `mcp__code-index__find_files` in Claude Code, where
`code-index` is the server key from the MCP configuration.

## Session setup

Call these before any file operation in a new session:

```
set_project_path(path="/absolute/path/to/project")
build_deep_index()
```

Both calls matter. `set_project_path` builds only the shallow index — a file list, enough for
`find_files` and `search_code_advanced`. `build_deep_index` is what extracts symbols, so
`get_file_summary`, `get_symbol_body`, and `called_by` stay empty or incomplete until it runs.
It takes a few seconds on most projects; on large codebases (3000+ files) `max_workers` and
`timeout` can be tuned.

Repeat both calls if the project path changes. Launching the server with `--project-path` is
equivalent to the first call only, so `build_deep_index` is still required.

For long sessions, let the watcher keep the index current instead of rebuilding by hand:

```
configure_file_watcher(enabled=true)
```

## Tool routing

| Operation | Instead of | Use |
|---|---|---|
| Find files by name or pattern | glob, `find`, `fd` | `find_files(pattern="*.py")` |
| Search code | grep, `rg`, `ag` | `search_code_advanced(pattern="...")` |
| List a directory | `ls`, `tree` | `find_files(pattern="src/*")` |
| Count files or lines | `wc`, `find \| wc` | `find_files` result count, or `get_file_summary` line count |
| Understand a file's structure | reading the whole file, `head` | `get_file_summary(file_path="...")` |
| Read one function, method, or class | read file, then scan | `get_symbol_body(file_path, symbol_name)` |
| Read a method on a class | read the whole class file | `get_symbol_body(file_path, "Class.method")` |
| Check imports | `grep import` | `get_file_summary` — imports are in the output |
| Find callers of a function | `grep "functionName"` | `get_symbol_body` returns `called_by`; follow it |
| Get edit context for a function | read file, find, edit | `get_symbol_body` for line numbers, then read that range |
| Resync after bulk edits | re-reading files | `refresh_index()` |

Shell commands that remain appropriate: `git log`, `git diff`, `git blame` (version control,
not file discovery), `stat` and `file` (metadata), and any build, test, or lint command that
happens to read files.

If a file-discovery or search tool is unavailable and the reflex is to shell out to
`grep -r`, `find . -name`, `ls src/`, `cat foo.py`, or `head -n 100 bar.ts` — use the
corresponding indexed tool instead. Shelling around the index returns unstructured text and
spends context for less information.

## Reading code

Follow this order. Reach for a plain file read only when the indexed tools cannot supply the
bytes needed.

1. **Path unknown?** Call `find_files` or `search_code_advanced` first. Do not guess paths.
2. **File structure not yet seen this session?** Call `get_file_summary` first, including when
   the goal is only to see what is in the file. The summary returns the function and class
   list, imports, and line count for a fraction of the tokens.
3. **Then match the need to the tool:**

| Need | Action |
|---|---|
| A specific function, method, or class body | `get_symbol_body(file_path, symbol_name)` |
| Several symbols from one file | One `get_symbol_body` call per symbol |
| Imports or exports only | Already in `get_file_summary` output |
| Callers of a function | `get_symbol_body` returns `called_by` |
| Line numbers for an edit | `get_symbol_body` returns `line`/`end_line`; read that range |
| A multi-symbol edit across a file | `get_file_summary` first, then read only the range to edit |
| A non-code file (JSON, YAML, Markdown, config, data) | Read it directly |

Reading a whole source file is a last resort. It is reasonable when a summary already gave the
line numbers and a specific range is needed for an edit, when the file is known to be short,
or when the indexer reported a parse error for that file.

### "What does this project do?"

This is the highest-risk prompt for wasted context. The reflex is to read `index.js`,
`__init__.py`, or `app.py` to see what is there. Entry-point files are usually re-export shims
or dispatcher glue: reading one returns a wall of imports and says little about the
architecture.

Instead:

1. `find_files(pattern="*")` at the project root for the top-level layout.
2. `find_files(pattern="src/**/*.py")`, or the equivalent for the language, to enumerate modules.
3. `get_file_summary` on the entry point and on three to five of the largest or most connected
   modules. These summaries are the architecture — classes, functions, imports, line counts.
4. `get_symbol_body` on whichever symbols the summaries suggest are central.
5. Only then read a small file end to end, if it is still necessary.

## Tool notes

`search_code_advanced` replaces grep and its shell equivalents, auto-selecting the fastest
available backend (ugrep, ripgrep, ag, or grep). Search is literal by default; pass
`regex=True` for patterns. Narrow with `file_pattern="*.py"`, set `case_sensitive=False` for
case-insensitive matching, `fuzzy=True` where ugrep is available, and `context_lines=2` for
surrounding lines. Results paginate through `max_results` (default 10) and `start_index`;
start small and page through large codebases.

`get_file_summary` returns line count, functions and classes with their line numbers, imports,
and complexity metrics.

`get_symbol_body` returns one symbol's signature, docstring, source, `line`/`end_line`, and
`called_by`. It accepts dot notation for members: `"ClassName.method_name"`. Check `status`
before trusting `code`.

## Delegating to subagents

Subagents do not inherit this skill. Include these instructions when dispatching one that
touches files:

```
Tool routing (code-index):
- Call set_project_path(path="<repo-root>") before any search
- Call build_deep_index() for symbol-aware results
- Use find_files instead of glob, find, fd, ls, or tree
- Use search_code_advanced instead of grep, rg, or ag
- Call get_file_summary before reading any source file for the first time
- Use get_symbol_body for targeted reads; dot notation works for members ("Class.method")
- Read files directly only for non-code files, or for a known range you are about to edit
- To find callers, use the called_by field from get_symbol_body rather than a text search
- Do not use shell commands for file discovery, code search, or code reading
```
