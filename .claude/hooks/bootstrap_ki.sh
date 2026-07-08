#!/usr/bin/env bash
# SessionStart hook: best-effort fetch of the Kirito interpreter so `.ki` tests can run in a fresh web
# session. Downloads the latest release `ki-linux-x64` to ./ki if it is not already present on PATH or
# in the repo. This is the pure-Kirito analog of the language repo's "build from source" step. It never
# fails the session — offline, or already-present, are both fine (exit 0 regardless).
set -u
cd "$(dirname "$0")/../.." 2>/dev/null || exit 0

# Already have an interpreter? Nothing to do.
if [ -x ./ki ]; then exit 0; fi
if command -v ki >/dev/null 2>&1; then exit 0; fi

URL="https://github.com/kiritolang/kiritolang.github.io/releases/latest/download/ki-linux-x64"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o ./ki "$URL" 2>/dev/null && chmod +x ./ki 2>/dev/null || rm -f ./ki
fi
exit 0
