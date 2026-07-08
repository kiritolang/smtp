# Post-work checklist

The routine to run **after every change, before declaring it done**. This is a pure-Kirito package, so
there is no C++/CMake build — the mechanics are `run_tests.sh` pointed at a `ki` interpreter.

## The routine

1. **Write tests for what changed.** Every new feature or fixed bug gets a focused test in the same
   change. Prefer many small tests over one big one.
   - Deterministic behaviour with known output → a self-asserting `tests/unit/NAME.ki` (uses `check()`
     + counters, prints `N passed, 0 failed`, exits non-zero on failure).
   - Code that *should fail* → `tests/errors/NAME.ki` + `NAME.experr` (each `.experr` line is a required
     substring of stderr; the program must exit non-zero). Cover the bad path, not just the good one.
   - **Regression-per-bug.** A fix ships an executable test the bug would have failed. Name it after the
     symptom, not a PR id (`spec_reply_split_boundary.ki`, not `fix_pr3.ki`).

2. **Run the whole suite against a real `ki`.**
   ```sh
   ./run_tests.sh --ki ./ki            # or any ki >= 1.13.0 (needs net.tlsenabled for the TLS live tests)
   ```
   The suite must end `ALL TESTS PASSED` / `0 failed` with exit 0. The nightly downloads the latest
   release binary and runs exactly this.

3. **Commit and push to the working `claude/…` branch once green.** Every commit and push goes to the
   `claude/…` feature branch only (enforced by `.claude/hooks/enforce_claude_branch.py`); never `main`.
   Push before any long-running follow-up so the work survives a container reset.

4. **Update docs in the same change.** `README.md` and any usage snippets must reflect reality. A
   feature without a matching doc update is not done.

## Notes

- The library is pure Kirito; it needs a `ki` binary with `net.tlsenabled == True` (the official release
  binaries qualify) for the STARTTLS/SMTPS live tests. Without TLS those live tests skip loudly; the rest
  of the suite still runs.
- `run_tests.sh` defaults `--ki` to `./ki` if present, else `ki` on PATH.
