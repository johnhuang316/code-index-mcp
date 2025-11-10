# MCP Upgrade Notes (November 2025)

## Why this upgrade matters
- `mcp` 1.21.0 was published to PyPI on 2025-11-06, so we are at least 17 point releases behind the current SDK and missing recent transport, auth, and client-surface fixes.
- The MCP governance group will cut the next specification release on 2025-11-25 (RC on 2025-11-11), so validating 1.21.0 now keeps us aligned ahead of another protocol bump.

## Dependency & packaging considerations
1. Run `uv lock --upgrade mcp` (or equivalent) so `uv.lock` stops pinning 1.4.1 and picks up the 1.21.0 wheels plus their refreshed transitive set (Starlette 0.49.1, AnyIO/HTTPX upgrades, etc.).
2. Re-run `uv run pytest` and our smoke commands (`uv run code-index-mcp --project-path <repo>`) because AnyIO cancellation semantics and Starlette ASGI changes can surface subtle regressions in watcher services.
3. Publish the lockfile and version bumps together; our release checklist requires pyproject + package __init__ + uv.lock to stay in sync.

## API & runtime changes to verify
- SEP-985 landed in 1.21.0, adding OAuth-protected resource metadata fallback: confirm our SettingsService handles `WWW-Authenticate` responses and that CLI flags surface any required bearer tokens.
- `ClientSession.get_server_capabilities()` is new; if clients or integration tests introspect capabilities manually, migrate to this helper.
- Starlette 0.49.1 ships tighter ASGI scope validation; double-check our SSE transport and progress notifications.

## Recommended practices for 1.21.x
1. **Depend on Context injection, not globals.** Annotate `ctx: Context` parameters so FastMCP injects the request context automatically instead of calling `mcp.get_context()` directly; this keeps us compatible with async-only handlers and future dependency-injection changes.
2. **Cache expensive tool listings in clients.** Newer agents (OpenAI Agents SDK, Claude Desktop) call `list_tools()` on every run; set `cache_tools_list=True` only when our tool roster is static and call `invalidate_tools_cache()` after deployments.
3. **Respect capability negotiation each session.** Protocol version 2025-06-18 remains current, and version negotiation happens during `initialize`; ensure our server exposes accurate `capabilities` metadata and gracefully errors when clients offer only future versions.
4. **Stay ahead of November spec changes.** The upcoming 2025-11-25 spec focuses on additional security hardening. Schedule time to exercise the RC (available 2025-11-11) so we can absorb any required surface changes early.
5. **Document OAuth and transport choices.** With SEP-985 and other auth SEPs in flight, record which flows (`device`, `jwt-bearer`, etc.) each deployment expects, and prefer the Streamable HTTP transport when exposing remote servers to benefit from the latest security guidance.

## Validation checklist before merging
- [ ] Lockfile regenerated (`uv lock --upgrade mcp`) and `uv run python -m code_index_mcp.server --help` still succeeds.
- [ ] `uv run code-index-mcp --project-path <repo>` exercises `set_project_path`, `build_deep_index`, and `search_code_advanced` end-to-end.
- [ ] Smoke Claude Desktop / Codex CLI against the upgraded server; confirm resources + tools enumerate and that tool caching behaves as expected.
- [ ] Update release notes + AGENTS.md summary once 1.21.x is verified in staging.
