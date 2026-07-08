#!/usr/bin/env python3
"""PreToolUse Bash hook: keep Claude's commits and pushes on a `claude/…` feature branch.

Adapted from the kiritolang.github.io hook. This repo's web sessions work on branches named
`claude/<slug>` (e.g. `claude/smtp-library-kirito-ieg4a9`), so the policy allows any branch whose name
starts with `claude/` and blocks:
  * a commit while HEAD is on any non-`claude/…` branch (e.g. `main`)
  * a push that leaves a `claude/…` branch, or that targets `main`

Contract (Claude Code hooks): read the tool call as JSON on stdin, decide, and either exit 0 to allow
the tool or exit 2 with a reason on stderr to block it. Only Bash `git push` / `git commit` invocations
are inspected; every other tool call passes through untouched. Detection uses `shlex` so that the words
"git push" appearing inside a quoted argument (e.g. a commit message body) do NOT trigger the rule.
"""
import json
import re
import shlex
import subprocess
import sys

BRANCH_PREFIX = "claude/"
PROTECTED = "main"


def read_command() -> str:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return ""
    return (data.get("tool_input") or {}).get("command") or ""


def tokens(cmd: str):
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return None


def _skip_git_options(tks, i):
    # After a `git` token, skip `-c key=val` / `--git-dir=...` style top-level options to reach the
    # subcommand token.
    j = i + 1
    while j < len(tks):
        t = tks[j]
        if t == "-c" and j + 1 < len(tks):
            j += 2
            continue
        if t.startswith("--") and "=" in t:
            j += 1
            continue
        break
    return j


def uses_git(op: str, cmd: str) -> bool:
    tks = tokens(cmd)
    if tks is not None:
        for i, t in enumerate(tks):
            if t == "git":
                j = _skip_git_options(tks, i)
                if j < len(tks) and tks[j] == op:
                    return True
        return False
    # Fallback: only trip when the command literally *starts* with `git <op>`.
    return bool(re.match(rf'\s*(?:[A-Za-z_]\w*=\S*\s+)*git(?:\s+-c\s+\S+)*\s+{op}\b', cmd))


def push_touches_protected(cmd: str) -> bool:
    tks = tokens(cmd)
    if tks is None:
        return bool(re.search(rf'(^|[\s:/]){PROTECTED}(\s|$|:)', cmd) or f"refs/heads/{PROTECTED}" in cmd)
    for i, t in enumerate(tks):
        if t != "git":
            continue
        j = _skip_git_options(tks, i)
        if j >= len(tks) or tks[j] != "push":
            continue
        for arg in tks[j + 1:]:
            if arg.startswith("-"):
                continue
            if arg == PROTECTED:
                return True
            if ":" in arg and arg.rsplit(":", 1)[1] == PROTECTED:
                return True
            if arg.endswith(f"refs/heads/{PROTECTED}"):
                return True
    return False


def current_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return ""


def allowed(br: str) -> bool:
    return br.startswith(BRANCH_PREFIX)


def deny(msg: str) -> None:
    print(f"blocked by claude-branch policy: {msg}", file=sys.stderr)
    print(
        f"hint: work only on a '{BRANCH_PREFIX}…' branch (see CLAUDE.md '## Git'); never commit on or "
        f"push to '{PROTECTED}'. Switch back with `git checkout {BRANCH_PREFIX}<slug>`.",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    cmd = read_command()
    if not cmd:
        sys.exit(0)

    if uses_git("push", cmd):
        if push_touches_protected(cmd):
            deny(f"git push targets '{PROTECTED}'; push only to a {BRANCH_PREFIX}… branch")
        br = current_branch()
        if br and not allowed(br):
            deny(f"current branch is '{br}'; push only from a {BRANCH_PREFIX}… branch")

    if uses_git("commit", cmd):
        br = current_branch()
        if br and not allowed(br):
            deny(f"current branch is '{br}'; commit only on a {BRANCH_PREFIX}… branch")

    sys.exit(0)


if __name__ == "__main__":
    main()
