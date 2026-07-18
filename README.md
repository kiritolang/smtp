# smtp — a complete SMTP library for [Kirito](https://github.com/kiritolang/kiritolang.github.io)

A from-scratch, pure-Kirito SMTP toolkit: a full **ESMTP client** with **real TLS** (STARTTLS and
implicit SMTPS), the complete **SASL authentication** set, **MIME** message building *and* parsing,
RFC 5321/5322 address handling, and a receiving **SMTP server** framework. No native code — it needs
only the Kirito standard library.

```kirito
var smtp = import("smtp")

var msg = smtp.MailBuilder().from_("me@example.com", "My Name").to("you@example.org", "You")
msg = msg.subject("Hello from Kirito ☕")
msg = msg.text("This was sent by a pure-Kirito SMTP client.")
msg = msg.html("<h1>Hello</h1><p>Sent by a <b>pure-Kirito</b> SMTP client.</p>")

smtp.send(msg, "smtp.example.com", username = "me@example.com", password = "app-password")
```

## Features

- **ESMTP client** — `EHLO`/`HELO` with capability parsing, `MAIL`/`RCPT`/`DATA`, `BDAT` (CHUNKING),
  `RSET`/`NOOP`/`VRFY`/`EXPN`/`HELP`/`QUIT`, per-recipient refusal handling, `with`-context support,
  and enhanced status codes (RFC 3463).
- **Real TLS** — `STARTTLS` (RFC 3207) and implicit **SMTPS** on port 465, with certificate
  verification (SNI + peer cert), reporting `is_tls()` / `cipher()`. Uses the interpreter's
  socket-level TLS (ki ≥ 1.13.0).
- **ESMTP extensions** — `SIZE`, `8BITMIME`, `BINARYMIME`, `SMTPUTF8`, `PIPELINING`, `CHUNKING`,
  `DSN` (delivery notifications), `ENHANCEDSTATUSCODES` — used only when the server advertises them.
- **SASL auth** — `PLAIN`, `LOGIN`, `CRAM-MD5`, `DIGEST-MD5`, `SCRAM-SHA-1`, `SCRAM-SHA-256`,
  `XOAUTH2`, `OAUTHBEARER`, `EXTERNAL`, `ANONYMOUS`, and `NTLM`. Strongest offered mechanism is chosen
  automatically; SCRAM verifies the server signature (MITM protection).
- **MIME** — `MailBuilder` composes text, HTML, attachments, and inline (`cid:`) images into the
  correct `multipart/mixed > related > alternative` tree, with base64 / quoted-printable / 7bit
  encodings, RFC 2047 header encoding, and RFC 2231 filename encoding. **Header/address injection is
  rejected.**
- **Message parsing** — `parse_message()` turns a raw message back into a headers + parts tree
  (round-trips what the builder emits), decoding transfer encodings and RFC 2047 words.
- **DKIM signing** — `dkim_sign()` adds an RFC 6376 `rsa-sha256` DKIM-Signature (relaxed/simple
  canonicalization) using the interpreter's public-key crypto. Requires **ki ≥ 1.14.1**
  (`crypto.enabled`).
- **Receiving server** — `SmtpServer` speaks the protocol (EHLO/MAIL/RCPT/DATA/BDAT/AUTH/…) and hands
  each accepted message to your `on_message` callback.

## Requirements

- **ki ≥ 1.13.0** (the release that introduced socket-level TLS). Check with
  `import("net").tlsenabled` — it must be `True` for STARTTLS / SMTPS. The official release binaries
  are TLS-enabled.
- **ki ≥ 1.14.1** for **DKIM signing** (needs the `crypto` module — `import("crypto").enabled`). The
  rest of the library works on 1.13.0.

Verified against ki **1.13.0 through 1.16.1** (the current release); the nightly runs the full suite on
`latest` plus pinned `1.16.1f` / `1.14.1` / `1.13.0`.

## Install

With the Kirito package manager:

```sh
kpm install kiritolang/smtp
```

Then `import("smtp")` from anywhere. To use a working copy without installing, put the repo root on
the import path: `ki --lib /path/to/smtp your_script.ki` (or set `KIRITO_PATH`).

## Sending mail

### One-liner

```kirito
var smtp = import("smtp")
smtp.sendmail("smtp.example.com", "me@example.com", "you@example.org",
              "Subject line", "Plain-text body",
              username = "me@example.com", password = "app-password")
```

### Rich messages with `MailBuilder`

```kirito
var msg = smtp.MailBuilder().from_("me@example.com", "My Name")
msg = msg.to("a@example.org").to("b@example.org", "Bee").cc("c@example.org")
msg = msg.bcc("hidden@example.org")               # in the envelope, never in the headers
msg = msg.reply_to("replies@example.com")
msg = msg.subject("Réunion 📅")                   # non-ASCII is RFC 2047-encoded
msg = msg.text("Plain-text alternative.")
msg = msg.html("<p>See the <img src='cid:logo'> below.</p>")
msg = msg.embed("logo.png", logo_bytes, "logo")   # inline image, referenced as cid:logo
msg = msg.attach("report.pdf", pdf_bytes)         # content type guessed from the name
msg = msg.header("X-Mailer", "kirito-smtp")

smtp.send(msg, "smtp.example.com", username = "me@example.com", password = "secret")
```

### Choosing transport security

`send(...)` takes `security =`:

| value        | meaning                                             | default port |
|--------------|-----------------------------------------------------|--------------|
| `"starttls"` | plaintext, then upgrade — **fails** if not offered  | 587 (default)|
| `"tls"`      | implicit TLS (SMTPS) from the first byte            | 465          |
| `"auto"`     | STARTTLS if offered, else plaintext                 | 587          |
| `"plain"`    | no encryption                                       | 587          |

```kirito
smtp.send(msg, "smtp.gmail.com", security = "starttls", username = u, password = p)
smtp.send(msg, "smtp.example.com", security = "tls")          # SMTPS on 465
smtp.send(msg, "localhost", port = 25, security = "plain")    # local relay
```

Certificate verification is **on by default** (`verify = True`); pass `verify = False` only for a
self-signed test server. `send()` returns a Dict of refused recipients (empty when all were accepted)
and raises an `SmtpError` on failure.

### OAuth2

```kirito
smtp.send(msg, "smtp.gmail.com", username = "me@gmail.com", password = oauth_token,
          auth_mechanism = "XOAUTH2")
```

### Low-level client

```kirito
var c = smtp.SmtpClient(host = "smtp.example.com", port = 587)
c.connect()
c.ehlo()
c.starttls()                       # verify=True by default
c.login("user", "pass")            # auto-selects the strongest mechanism
var refused = c.sendmail("me@example.com", ["you@example.org"], msg.build(),
                         c.mail_options(size = 4096), c.rcpt_options(notify = "FAILURE"))
c.quit()
```

## Parsing messages

```kirito
var part = smtp.parse_message(raw_bytes_or_string)
part.header("subject")                     # raw header
smtp.parse_message(raw).header_decoded("subject")  # RFC 2047-decoded
for leaf in part.walk_leaves():
    import("io").print(leaf.content_type, leaf.filename())
```

## Receiving mail

```kirito
var server = import("smtp.server")
var handler = Function(sender, recipients, data):
    import("io").print("got", len(data), "bytes from", sender, "for", recipients)
    return True                              # accept

var srv = server.SmtpServer("0.0.0.0", 2525, handler)
srv.serve_forever()
```

The server is **plaintext** (see limitations). For AUTH, pass an `auth_lookup(username) -> password`
function; it then advertises and verifies `AUTH PLAIN/LOGIN/CRAM-MD5`.

## DKIM signing

Requires **ki ≥ 1.14.1** (`import("crypto").enabled`). `dkim_sign()` prepends an RFC 6376 `rsa-sha256`
DKIM-Signature (relaxed canonicalization by default):

```kirito
var signed = smtp.dkim_sign(msg.build(), "example.com", "selector1", private_key_pem)
smtp.send(signed, "smtp.example.com", from_addr = "me@example.com", to = "you@example.org",
          security = "starttls")
```

Or sign as part of `send()`:

```kirito
smtp.send(msg, "smtp.example.com", username = u, password = p,
          dkim = {"domain": "example.com", "selector": "selector1", "private_key": private_key_pem})
```

`smtp.dkim_verify(message, public_key_pem)` checks a signature against an explicitly-supplied public
key (the interpreter's `net` can't do DNS `TXT` lookups, so live `selector._domainkey` retrieval is out
of scope). Publish the matching public key at `selector1._domainkey.example.com` as usual.

## Security model

- TLS certificate verification is on by default; the peer certificate and hostname (SNI) are checked.
- **Header and command injection are blocked**: any `CR`/`LF`/`NUL` in a header value, display name,
  address, or command argument is rejected before anything is sent.
- SCRAM verifies the server's signature, detecting a man-in-the-middle.
- The fuzz + adversarial suites assert the client only ever raises a typed `SmtpError` — never an
  uncaught crash — on malformed or hostile server behaviour.

## Limitations & scope

Everything the SMTP / ESMTP / SASL / MIME surface needs is included. The remaining limits are
interpreter/API constraints, not the library:

- **S/MIME and PGP** are not implemented. As of ki 1.14.1 the `crypto` module makes them *feasible* in
  principle (RSA/EC + AES + `x509parse` are available), but they need substantial CMS/ASN.1 (S/MIME) or
  OpenPGP-packet work that is out of scope here. **DKIM is implemented** (`dkim_sign`, ki ≥ 1.14.1).
- **Server-side TLS**: the interpreter's socket TLS is client-side only, so a Kirito `SmtpServer` is
  plaintext. Put it behind [stunnel](https://www.stunnel.org/) for SMTPS.
- **SCRAM `-PLUS` channel binding** is out of reach because the socket API exposes no TLS
  channel-binding material (`tls-unique` / `tls-server-end-point`).
- **DKIM key retrieval by DNS** — `net` can't do arbitrary `TXT` lookups, so `dkim_verify` takes the
  public key explicitly rather than resolving `selector._domainkey`.

## Package layout

Modules are flat files named with their dotted import name (how ki resolves package modules):

| module | purpose |
|---|---|
| `smtp` | facade: `send`/`sendmail`, `SmtpClient`, `SmtpServer`, `MailBuilder`/`Message`, `parse_message`, errors |
| `smtp.client` | ESMTP client state machine |
| `smtp.server` | receiving server framework |
| `smtp.transport` | `PlainTransport` (net.Socket + TLS) / `FakeTransport` / `LineReader` |
| `smtp.auth` | SASL mechanisms + server verifiers |
| `smtp.hmac`, `smtp.md4` | HMAC/PBKDF2 and MD4 (for the SASL mechanisms) |
| `smtp.message`, `smtp.mime` | MIME message building + encoders |
| `smtp.msgparse` | message parser |
| `smtp.address` | address parsing/formatting/validation |
| `smtp.parse` | SMTP reply-grammar parsing |
| `smtp.dkim` | DKIM signing/verification (RFC 6376, needs `crypto`) |
| `smtp.errors` | the `SmtpError` hierarchy |

## Testing

```sh
curl -fsSL -o ki https://github.com/kiritolang/kiritolang.github.io/releases/latest/download/ki-linux-x64
chmod +x ki
./run_tests.sh --ki ./ki
```

Runs the self-asserting unit suite (crypto/SASL against RFC vectors, MIME round-trips, DKIM, the client
state machine, adversarial + seeded fuzz tests), the error-message suite, a pure-Kirito live loopback
test, and — if `python3` is present — the real-TLS harness (STARTTLS + SMTPS against a mock server) and
a DKIM interop check that verifies a Kirito-signed message with an independent `openssl` verifier. The
nightly GitHub Actions workflow runs all of this against the latest `ki` release.

## License

See [LICENSE](LICENSE).
