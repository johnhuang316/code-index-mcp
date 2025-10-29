## 2.5.1 - Relative Symbol IDs

### Highlights
- Deep index symbol identifiers now use project-relative paths, preventing SQLite uniqueness collisions during rebuilds.
- Added regression coverage to ensure duplicate filenames across directories generate distinct symbol IDs.
- Release notes migrated to Markdown for easier editing.

### Notes
- Triggering a deep index rebuild will automatically regenerate symbol identifiers for existing caches.

## 2.5.0 - SQLite Deep Index & Middleware Coverage

### Highlights
- Deep index now persists to SQLite via the new `SQLiteIndexStore`, replacing the legacy JSON cache while keeping build performance stable.
- JavaScript strategy records middleware callbacks in the call graph, giving accurate `called_by` links for Express-style handlers.
- TypeScript strategy captures limiter callbacks, closing gaps for `.ts` middleware exports and aligning coverage with JavaScript.
- Added dedicated regression tests for the SQLite store/manager plus JavaScript and TypeScript call graph fixtures.

### Notes
- Existing JSON deep index files are ignored; rebuilds transparently populate the SQLite database under `%TEMP%/code_indexer/<project_hash>/`.

## 2.4.1 - Search Filtering Alignment

### Highlights
- Code search now shares the central FileFilter blacklist, keeping results consistent with indexing (no more `node_modules` noise).
- CLI search strategies emit the appropriate exclusion flags automatically (ripgrep, ugrep, ag, grep).
- Basic fallback search prunes excluded directories during traversal, avoiding unnecessary IO.
- Added regression coverage for the new filtering behaviour (`tests/search/test_search_filters.py`).
