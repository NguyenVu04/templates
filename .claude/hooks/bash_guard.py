"""PreToolUse hook (Bash): block package managers this repo does not use, and
block staging model/data artifacts that belong to DVC or MLflow rather than git.

Fails open on anything unexpected.

    echo '{"tool_input":{"command":"pip install torch"}}' | python bash_guard.py
"""

import json
import os
import re
import subprocess
import sys

# Model and data artifacts that must never enter git history.
ARTIFACT_EXT = (".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".joblib", ".pkl", ".h5")
ARTIFACT_DIRS = ("mlruns/", "wandb/", "outputs/", "multirun/")
SIZED_EXT = (".csv", ".parquet", ".feather", ".npy")  # denied only when large
SIZE_LIMIT = 5 * 1024 * 1024

BANNED = [
    (r"\bpip3?\s+install\b", "pip install", "uv add <package>  (or `task setup` / `task sync`)"),
    (r"\bpython\s+-m\s+pip\s+install\b", "python -m pip install", "uv add <package>"),
    (r"\bconda\s+(install|create)\b", "conda", "uv add <package>  /  uv venv"),
    (r"\bpoetry\s+(add|install)\b", "poetry", "uv add <package>  /  uv sync"),
    (r"\bpython\s+-m\s+venv\b", "python -m venv", "uv venv  (or `task setup`)"),
]


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def segments(command):
    """Split a compound command so `uv run pip install -e .` is judged as one unit."""
    return [s.strip() for s in re.split(r"&&|\|\||[;|]", command) if s.strip()]


def check_package_managers(command):
    for seg in segments(command):
        if re.match(r"^(uv|task)\b", seg):
            continue  # `uv run pip install -e .` and `task setup` are the sanctioned paths
        for pattern, what, instead in BANNED:
            if re.search(pattern, seg):
                deny(
                    "`{}` is not used in this repository -- it manages Python with uv, and "
                    "commands go through Task. Use:  {}\nSee `.claude/rules/python-ml.md` and "
                    "machine-learning/Taskfile.yml. If you genuinely need the raw command, "
                    "prefix it with `uv run`.".format(what, instead)
                )


def is_artifact(path, root):
    lower = path.lower()
    if lower.endswith(ARTIFACT_EXT):
        return "a model artifact ({})".format(os.path.splitext(lower)[1])
    for d in ARTIFACT_DIRS:
        if lower.startswith(d) or "/" + d in lower:
            return "run output under {}".format(d)
    if lower.endswith(SIZED_EXT):
        try:
            size = os.path.getsize(os.path.join(root, path))
        except OSError:
            return None
        if size > SIZE_LIMIT:
            return "a {:.1f} MB data file".format(size / 1024 / 1024)
    return None


def staged_paths(command, root):
    """Paths a `git add`/`git commit -a` would stage. Reads git state, changes nothing."""
    add = re.search(r"\bgit\s+add\s+(.+)$", command)
    if add:
        args = [a for a in add.group(1).split() if not a.startswith("-")]
        wildcard = re.search(r"\bgit\s+add\s+(-A|--all|-u|\.)\b", command)
        if args and not wildcard:
            return [a.strip("'\"") for a in args]
    elif not re.search(r"\bgit\s+commit\b.*\s-\w*a", command):
        return []
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True,
            text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line[3:].strip().strip('"') for line in out.stdout.splitlines() if line[3:].strip()]


def check_git(command, root):
    if not re.search(r"\bgit\s+(add|commit)\b", command):
        return
    offenders = []
    for path in staged_paths(command, root):
        if path.endswith(".dvc") or path.endswith(".gitignore"):
            continue
        why = is_artifact(path.replace("\\", "/"), root)
        if why:
            offenders.append("  {}  -- {}".format(path, why))
    if offenders:
        deny(
            "This would commit build products of training, not the rules that produced them:\n"
            + "\n".join(offenders[:10])
            + "\n\nThree versioning layers keep these separate: DVC versions file contents, git "
            "plus the Hydra YAML versions the rules, MLflow versions the runs. Track data with "
            "`dvc add` and commit the `.dvc` pointer; leave `mlruns/` and checkpoints to MLflow. "
            "If one of these really belongs in git, add it by explicit path and say why."
        )


def main():
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        return
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    check_package_managers(command)
    check_git(command, root)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open
    sys.exit(0)
