---
paths:
  - ".claude/skills/**/*.md"
  - ".claude/rules/**/*.md"
  - ".claude/hooks/**"
---

# Extending the skills, rules and hooks

## Skills: the router pattern

Every multi-topic skill here is one router `SKILL.md` plus a `references/` directory. The router
holds routing and cross-cutting rules; the depth lives in the reference files.

- **`SKILL.md` stays under 500 lines** and contains: frontmatter, a routing table, the
  cross-cutting rules that govern every phase, and cross-links to sibling skills. If it starts
  explaining *how* to do something, that content belongs in a reference file.
- **`description` + `when_to_use` must total ≤ 1,536 characters.** Claude Code truncates past
  that, and drops descriptions entirely when the whole listing overflows its budget. When
  trimming, cut prose and keep trigger keywords — **including the Vietnamese ones**, which are
  what make these skills fire on how this repository's user actually writes.
- Reference files carry **no frontmatter**. They are loaded by the router, not listed as skills.
- **No content is duplicated between two reference files.** State it once and link to it.
- Same-router links are relative (`[training.md](training.md)`). Cross-router references name the
  skill and the file (see the `machine-learning` skill, `references/statistics.md`) — a `../../`
  path is unreadable and breaks if a skill is renamed.
- Nesting is not a grouping mechanism: skills are discovered at `.claude/skills/<name>/SKILL.md`
  only. Grouping means router + `references/`, never `skills/group/sub/SKILL.md`.

## Rules

- One topic per file. Anything not needed in *every* session gets `paths:` frontmatter so it
  loads only when Claude touches a matching file.
- Only `ai-ml-routing.md` loads unconditionally, and it is deliberately short. Adding another
  always-on rule costs context in every session, including sessions about Go or documentation.
- Rules are context, not enforcement. If a rule must actually hold, back it with a hook.

## Hooks

- Hook scripts are stdlib-only Python 3 in `.claude/hooks/`, no third-party imports and no
  network access.
- **Every script fails open.** Unparseable stdin, a missing tool, any unexpected exception →
  exit 0 with no output. A hook that breaks the session is worse than a hook that does nothing.
- Only `write_guard.py` and `bash_guard.py` may deny, and only on their specific narrow
  conditions. Every deny message must name the rule that was violated and the correct
  alternative — a block the user cannot act on is a bug.
- After changing a hook, run it against sample stdin (see the header comment in each script) and
  confirm both the trigger and the fail-open path.
