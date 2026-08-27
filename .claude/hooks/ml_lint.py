"""PostToolUse hook (Write|Edit): run ruff on Python files under machine-learning/.

Advisory -- it reports, it never blocks. ruff is configured in
machine-learning/pyproject.toml with pydocstyle `D` (google convention) and line
length 100, so this is the repository's documented lint standard applied without
being asked for.

Deliberately does nothing when machine-learning/.venv is absent: running
`uv run` there would install an environment as a side effect of an edit.

Fails open on anything unexpected.

    echo '{"tool_input":{"file_path":"machine-learning/src/x.py"}}' | python ml_lint.py
"""

import json
import os
import subprocess
import sys

PROJECT = "machine-learning"


def main():
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    path = payload.get("tool_input", {}).get("file_path", "")
    if not path.endswith(".py"):
        return
    posix = path.replace("\\", "/")
    if PROJECT + "/" not in posix + "/":
        return

    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    cwd = os.path.join(root, PROJECT)
    if not os.path.isdir(os.path.join(cwd, ".venv")):
        return  # no environment yet; do not trigger an install from an edit

    target = os.path.abspath(path if os.path.isabs(path) else os.path.join(root, path))
    report = []
    for args, label in (
        (["run", "ruff", "check", "--fix", target], "ruff check --fix"),
        (["run", "ruff", "format", target], "ruff format"),
    ):
        try:
            proc = subprocess.run(
                ["uv"] + args, cwd=cwd, capture_output=True, text=True, timeout=45
            )
        except (OSError, subprocess.SubprocessError):
            return  # uv or ruff unavailable: silent
        out = (proc.stdout + proc.stderr).strip()
        if proc.returncode != 0 or "error" in out.lower():
            report.append("{}:\n{}".format(label, out))

    if report:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "ruff on {} reported issues that auto-fix did not resolve. Fix them before "
                    "moving on -- docstrings are linted in this repository "
                    "(see `.claude/rules/python-ml.md`).\n\n{}".format(
                        posix, "\n\n".join(report)[:4000]
                    )
                ),
            }
        }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open
    sys.exit(0)
