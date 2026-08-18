# Project Skills

This repository exposes project-scoped skills from `.agents/skills`.

| Skill | Use when |
|---|---|
| `release-prep` | A completed change is ready for versioning or release work. |
| `verify-multilang-support` | Language strategies, parsers, indexing, or sample-project baselines need verification. |

Agents that support the `.agents/skills/<name>/SKILL.md` convention discover these
skills at session startup. Restart or open a new session after adding, renaming, or
changing a skill's frontmatter. Invoke a skill by name when deterministic selection
is important.
