"""PreToolUse hook (Write|Edit): block writes that would corrupt skill metadata
or overwrite a frozen test split.

Two narrow jobs, everything else passes straight through:

1. `.claude/skills/*/SKILL.md` and `.claude/rules/*.md` -- validate the resulting
   content's frontmatter. See `.claude/rules/skill-authoring.md` for the rules.
2. Frozen test splits -- deny writes to FROZEN_SPLIT_PATTERNS below. Edit that
   list for the project; it is inert in the templates repo, which has no data.

Coverage limit: `Write` carries full content and is validated exactly. `Edit`
carries only old_string/new_string, so the replacement is applied to the on-disk
file in memory; if the file cannot be read the hook exits 0 rather than guessing.

Fails open on anything unexpected.

    echo '{"tool_name":"Write","tool_input":{"file_path":"x","content":"y"}}' | python write_guard.py
"""

import fnmatch
import json
import os
import re
import sys

FROZEN_SPLIT_PATTERNS = [
    "**/data/processed/test*",
    "**/data/splits/**",
    "**/*test_split*",
]

MAX_DESC_CHARS = 1536  # description + when_to_use, per Claude Code's listing cap
MAX_SKILL_LINES = 500


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def parse_frontmatter(text):
    """Return (dict, n_lines) or (None, n) when there is no closing delimiter."""
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None, len(text.splitlines())
    data, key = {}, None
    for line in m.group(1).split("\n"):
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            key, val = km.group(1), km.group(2).strip()
            data[key] = "" if val in (">-", ">", "|", "|-", "") else val
        elif key and line.strip():
            data[key] = (data[key] + " " + line.strip()).strip()
    return data, len(text.splitlines())


def check_skill(path, text):
    directory = os.path.basename(os.path.dirname(path))
    fm, n_lines = parse_frontmatter(text)
    if fm is None:
        deny(
            "{}: YAML frontmatter is missing or its closing `---` is absent. A SKILL.md "
            "without valid frontmatter is not loaded as a skill at all.".format(path)
        )
    name = fm.get("name", directory)
    if name != directory:
        deny(
            "{}: frontmatter `name: {}` does not match the directory `{}`. They must match, "
            "or the skill is invoked under a name nobody expects.".format(path, name, directory)
        )
    if not fm.get("description"):
        deny(
            "{}: `description` is empty or missing. It is what Claude matches the user's "
            "request against -- without it the skill never fires automatically.".format(path)
        )
    budget = len(fm.get("description", "")) + len(fm.get("when_to_use", ""))
    if budget > MAX_DESC_CHARS:
        deny(
            "{}: description + when_to_use is {} characters, over the {} cap. Claude Code "
            "truncates past that, silently dropping the trigger keywords at the end. Cut prose, "
            "keep trigger keywords -- including the Vietnamese ones. See "
            "`.claude/rules/skill-authoring.md`.".format(path, budget, MAX_DESC_CHARS)
        )
    if n_lines > MAX_SKILL_LINES:
        deny(
            "{}: {} lines, over the {}-line router limit. A router holds routing plus "
            "cross-cutting rules; move the detail into `references/`.".format(
                path, n_lines, MAX_SKILL_LINES
            )
        )
    skill_dir = os.path.dirname(path)
    for link in re.findall(r"\]\(([\w./-]+\.md)\)", text):
        if not os.path.exists(os.path.join(skill_dir, link)):
            deny(
                "{}: links to `{}`, which does not exist. Every relative link in a router "
                "must resolve.".format(path, link)
            )


def check_rule(path, text):
    fm, _ = parse_frontmatter(text)
    if fm is None:
        if text.lstrip().startswith("---"):
            deny(
                "{}: frontmatter opens with `---` but never closes. An unterminated block "
                "makes the whole rule unparseable.".format(path)
            )
        return  # a rule with no frontmatter is valid: it loads unconditionally
    if "paths" in fm and not re.search(r"^paths:\s*\n(\s*-\s+\S+\n)+", text, re.M):
        deny(
            "{}: `paths:` must be a YAML list of quoted glob patterns, one `- \"...\"` per "
            "line. A malformed `paths:` makes the rule load in every session instead of the "
            "matching ones.".format(path)
        )


def resulting_content(tool_name, ti):
    if tool_name == "Write":
        return ti.get("content", "")
    path = ti.get("file_path", "")
    with open(path, encoding="utf-8") as fh:
        current = fh.read()
    old, new = ti.get("old_string", ""), ti.get("new_string", "")
    return current.replace(old, new) if ti.get("replace_all") else current.replace(old, new, 1)


def main():
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    ti = payload.get("tool_input", {})
    path = ti.get("file_path", "")
    if not path:
        return
    posix = path.replace("\\", "/")

    for pattern in FROZEN_SPLIT_PATTERNS:
        if fnmatch.fnmatch(posix, pattern) or fnmatch.fnmatch(posix, "*/" + pattern.lstrip("*/")):
            deny(
                "{} matches a frozen test-split pattern ({}). The test split stays frozen until "
                "the final evaluation, which happens exactly once -- see "
                "`.claude/rules/experiments.md`. If regenerating the split is genuinely intended, "
                "say so and ask first.".format(path, pattern)
            )

    is_skill = re.search(r"\.claude/skills/[^/]+/SKILL\.md$", posix)
    is_rule = re.search(r"\.claude/rules/[^/]+\.md$", posix)
    if not (is_skill or is_rule):
        return
    try:
        text = resulting_content(payload.get("tool_name", ""), ti)
    except OSError:
        return  # cannot reconstruct the result -- do not guess, let it through
    (check_skill if is_skill else check_rule)(path, text)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open
    sys.exit(0)
