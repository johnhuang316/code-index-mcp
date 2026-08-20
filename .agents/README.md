# Project Skills

This repository exposes project-scoped skills from `.agents/skills`.

| Skill | Use when |
|---|---|
| `code-index-first` | An agent is searching or reading code and should route through the code-index tools instead of grep, find, or whole-file reads. |
| `release-prep` | A completed change is ready for versioning or release work. |
| `verify-multilang-support` | Language strategies, parsers, indexing, or sample-project baselines need verification. |

Agents that support the `.agents/skills/<name>/SKILL.md` convention discover these
skills at session startup. Restart or open a new session after adding, renaming, or
changing a skill's frontmatter. Invoke a skill by name when deterministic selection
is important.

`code-index-first` is the only skill here aimed at users of this server rather than at
its maintainers; see [Agent Skills](../README.md#agent-skills) in the main README for how
to install it into another project.
