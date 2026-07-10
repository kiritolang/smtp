#!/usr/bin/env bash
# Run the whole smtp test suite against a chosen ki interpreter (>= 1.13.0).
#
#   ./run_tests.sh [--ki PATH]
#
# Default ki: ./ki if present, else `ki` on PATH. Runs the self-asserting unit tests, the error-message
# suite (.ki + .experr), the pure-Kirito live loopback test, and — if python3 is present — the real-TLS
# harness (STARTTLS + SMTPS). Exits non-zero if anything fails.
set -u
REPO="$(cd "$(dirname "$0")" && pwd)"

KI=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ki) KI="${2:-}"; shift 2 ;;
    --ki=*) KI="${1#--ki=}"; shift ;;
    -h|--help) echo "usage: $0 [--ki PATH]"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [ -z "$KI" ]; then
  if [ -x "$REPO/ki" ]; then KI="$REPO/ki"; else KI="ki"; fi
fi
if [ -f "$KI" ]; then KI="$(cd "$(dirname "$KI")" && pwd)/$(basename "$KI")"; fi
export KIRITO_PATH="$REPO:$REPO/tests"

echo "== smtp test suite =="
echo "ki: $KI"
"$KI" --version 2>/dev/null || { echo "ERROR: cannot run ki at '$KI'" >&2; exit 2; }
tlsfile="$(mktemp --suffix=.ki)"
printf 'import("io").print("net.tlsenabled:", import("net").tlsenabled)\n' > "$tlsfile"
"$KI" "$tlsfile" 2>/dev/null || true
rm -f "$tlsfile"
echo ""

fail=0

echo "-- unit tests --"
for f in "$REPO"/tests/unit/*.ki; do
  if out=$("$KI" "$f" 2>&1); then
    echo "  PASS $(basename "$f"): $(echo "$out" | grep -E 'passed,.*failed' | tail -1)"
  else
    echo "  FAIL $(basename "$f")"
    echo "$out" | tail -8 | sed 's/^/      /'
    fail=1
  fi
done

echo "-- error-message suite --"
for ki in "$REPO"/tests/errors/*.ki; do
  experr="${ki%.ki}.experr"
  out=$("$KI" "$ki" 2>&1); code=$?
  ok=1
  [ "$code" -eq 0 ] && ok=0
  if [ -f "$experr" ]; then
    while IFS= read -r want; do
      [ -z "$want" ] && continue
      echo "$out" | grep -qF -- "$want" || ok=0
    done < "$experr"
  fi
  if [ "$ok" -eq 1 ]; then
    echo "  PASS $(basename "$ki")"
  else
    echo "  FAIL $(basename "$ki") (exit $code)"
    echo "$out" | tail -4 | sed 's/^/      /'
    fail=1
  fi
done

echo "-- live loopback (pure Kirito) --"
if out=$(timeout 90 "$KI" "$REPO"/tests/live_plain.ki 2>&1); then
  echo "  PASS $(echo "$out" | grep -E 'passed,.*failed' | tail -1)"
else
  echo "  FAIL live_plain.ki"
  echo "$out" | tail -8 | sed 's/^/      /'
  fail=1
fi

echo "-- live TLS harness (STARTTLS + SMTPS) --"
if command -v python3 >/dev/null 2>&1; then
  if timeout 180 python3 "$REPO"/tests/test_smtp_live.py --ki "$KI"; then
    echo "  PASS tls harness"
  else
    echo "  FAIL tls harness"
    fail=1
  fi
else
  echo "  SKIP (python3 not found)"
fi

echo "-- DKIM interop (independent openssl verify) --"
if command -v python3 >/dev/null 2>&1; then
  if timeout 120 python3 "$REPO"/tests/test_dkim_interop.py --ki "$KI"; then
    echo "  PASS dkim interop"
  else
    echo "  FAIL dkim interop"
    fail=1
  fi
else
  echo "  SKIP (python3 not found)"
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "ALL TESTS PASSED"
else
  echo "TESTS FAILED"
fi
exit "$fail"
