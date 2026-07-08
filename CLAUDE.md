# CLAUDE.md — Claude Code instructions for `kiritolang/smtp`

**Read this file in full at the start of every session before doing anything else.**

## What this is

**`smtp`** — a complete, from-scratch **SMTP library written in pure [Kirito](https://github.com/kiritolang/kiritolang.github.io)**,
distributed as a `kpm` package. It provides a full ESMTP **client** (with real TLS — STARTTLS and
implicit SMTPS — AUTH/SASL, and MIME message building + parsing), address handling, and a receiving
**SMTP server** framework. It depends only on the Kirito standard library (`net`, `base64`, `hash`,
`regex`, `random`, `io`, and `parallel` for the server).

Source files use the `.ki` extension. The public module is `import("smtp")` with submodules
`import("smtp.client")`, `import("smtp.message")`, etc.

## Git

**ONLY commit and push to the `claude/…` feature branch** you were started on (this repo:
`claude/smtp-library-kirito-ieg4a9`). Pushing to `main` — or committing on it — is forbidden. The
cycle is: work on the `claude/…` branch, open a pull request, wait for the human to merge.

A PreToolUse hook (`.claude/hooks/enforce_claude_branch.py`, wired in `.claude/settings.json`) enforces
this: it blocks any `git commit` off a `claude/…` branch and any `git push` that leaves it or targets
`main`. If it fires, switch back to the `claude/…` branch — do not bypass it.

If the branch's previous PR has already merged, restart it fresh from `origin/main`
(`git fetch origin main && git checkout -B <branch> origin/main`); otherwise keep the existing unmerged
work on it.

## The interpreter (`ki`)

This package is *run*, not compiled. Get a `ki` interpreter (>= **1.13.0**, which introduced socket-level
TLS — `net.tlsenabled` must be `True` for the STARTTLS/SMTPS live tests):

```sh
curl -fsSL -o ./ki https://github.com/kiritolang/kiritolang.github.io/releases/latest/download/ki-linux-x64
chmod +x ./ki
```

The SessionStart hook (`.claude/hooks/bootstrap_ki.sh`) does this automatically, best-effort, on session
start. `./ki` is gitignored.

## Build & test

There is no build. Run the whole suite against a `ki`:

```sh
./run_tests.sh --ki ./ki
```

It runs the self-asserting `tests/unit/*.ki`, the `tests/errors/*.ki` + `.experr` suite, the pure-Kirito
loopback live test, and — if `python3` is present — the STARTTLS/SMTPS live harness
(`tests/test_smtp_live.py`). During tests, `KIRITO_PATH` is set to the repo root so `import("smtp")`
resolves to the working tree rather than an installed copy.

**Before claiming a change done, run `run_tests.sh` and report real output.** See
`.claude/POST_WORK_CHECKLIST.md`.

## Layout

Modules are **flat files at the repo root named with the dotted import name** (this is how `ki`
resolves package modules: `import("smtp.client")` looks for a file literally named `smtp.client.ki` on
the path — it does NOT translate dots to slashes). Cross-module imports use the full dotted name.

```
smtp.ki            facade: send(), SmtpClient, SmtpServer, MailBuilder, Message, parse_message(), errors
smtp.client.ki     SmtpClient — full ESMTP client state machine
smtp.server.ki     SmtpServer — receiving SMTP server framework (plaintext)
smtp.transport.ki  Transport / PlainTransport(net.Socket) / FakeTransport(test double) + LineReader
smtp.auth.ki       SASL mechanisms (client + server)
smtp.hmac.ki       HMAC-MD5/SHA1/SHA256 + PBKDF2
smtp.md4.ki        pure-Kirito MD4 (NTLM only)
smtp.message.ki    MailBuilder / Message — build a MIME tree
smtp.mime.ki       encoders/decoders (base64 wrap, quoted-printable, RFC 2047/2231, header folding)
smtp.msgparse.ki   raw message -> headers + nested parts (round-trips message.build)
smtp.address.ki    RFC 5321/5322 address parse/format/validate + SMTPUTF8
smtp.parse.ki      SMTP reply-line / multiline / EHLO capability / enhanced status codes
smtp.errors.ki     exception hierarchy (SmtpError base)
tests/             unit (self-asserting), errors (.ki+.experr), live_*.ki, mock server + Python harness
```

Tests run with `KIRITO_PATH=<repo-root>` so `import("smtp.*")` resolves to the working tree.

## Conventions

- **Kirito's public surface is lowercase, no underscores** (`sendmail`, `starttls`, `parse_message`).
  Keep new public names consistent; `_`-prefixed module/instance members are private.
- Classes: `class Foo:` with `var _init_ = Function(self, ...):` methods, significant indentation.
- Use `discard EXPR` for a call made only for its side effects that returns a non-`None` value (else the
  analyzer warns). Don't leave unused function-local variables.
- Errors are typed: `throw SmtpResponseError(...)`, caught with `catch smtp.errors.SmtpError as e`.
- **Security:** never let a caller inject SMTP commands or extra headers — reject `\r`/`\n` in every
  header value, address, and command argument.

## Scope

Everything the SMTP/ESMTP/SASL/MIME surface needs and that pure Kirito can express is in scope. The only
exclusions are features that require **public-key cryptography** (DKIM, S/MIME, PGP) — they need
RSA/Ed25519 (arbitrary-precision modular exponentiation), which Kirito's fixed int64 cannot do. A
signing-hook seam is left for them. Server-side TLS and SASL `-PLUS` channel binding are limited by the
interpreter's socket API (documented in `README.md`).

## Keep this file current

When a change alters the design, layout, or workflow, update this file in the same change.
