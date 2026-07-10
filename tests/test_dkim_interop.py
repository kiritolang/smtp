#!/usr/bin/env python3
"""Independent DKIM verifier (RFC 6376, rsa-sha256) — deliberately NOT the Kirito implementation. It
runs tests/dkim_gen.ki (via --ki) to obtain a message signed by smtp.dkim plus the public key, then
re-canonicalizes per RFC 6376 (pure Python), hashes the body with stdlib hashlib, and verifies the RSA
signature with the `openssl` CLI (independent of Kirito's crypto). Two from-scratch implementations
agreeing is the interoperability check. Skips (pass) if the ki build has no crypto or openssl is
missing. Usage: python3 tests/test_dkim_interop.py --ki /path/to/ki
"""
import argparse
import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def split_msg(m):
    i = m.find("\r\n\r\n")
    if i >= 0:
        return m[:i], m[i + 4:]
    j = m.find("\n\n")
    if j >= 0:
        return m[:j], m[j + 2:]
    return m, ""


def parse_headers(head):
    head = head.replace("\r\n", "\n").replace("\r", "\n")
    hs = []
    for ln in head.split("\n"):
        if ln[:1] in (" ", "\t") and hs:
            name, val, raw = hs[-1]
            hs[-1] = (name, val + " " + ln.strip(), raw + "\r\n" + ln)
        else:
            c = ln.find(":")
            if c > 0:
                hs.append((ln[:c].strip().lower(), ln[c + 1:].strip(), ln))
    return hs


def relax(v):
    return re.sub(r"[ \t]+", " ", v).strip()


def canon_header(mode, name, value, raw):
    return raw if mode == "simple" else name + ":" + relax(value)


def canon_body(mode, body):
    b = body.replace("\r\n", "\n").replace("\r", "\n")
    if mode == "simple":
        b = b.rstrip("\n")
        return (b.replace("\n", "\r\n") + "\r\n").encode()
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip(" \t") for ln in b.split("\n")]
    text = "\n".join(lines).rstrip("\n")
    if text == "":
        return b""
    return (text.replace("\n", "\r\n") + "\r\n").encode()


def parse_tags(v):
    out = {}
    for seg in v.split(";"):
        s = seg.strip()
        if "=" in s:
            k, val = s.split("=", 1)
            out[k.strip()] = val.strip()
    return out


def empty_b(value):
    out = []
    for p in value.split(";"):
        if p.strip().startswith("b="):
            lead = p[:len(p) - len(p.lstrip(" \t"))]
            out.append(lead + "b=")
        else:
            out.append(p)
    return ";".join(out)


def openssl_verify(pubpem, data_bytes, sig_bytes):
    d = tempfile.mkdtemp()
    try:
        pub = os.path.join(d, "pub.pem")
        dat = os.path.join(d, "data.bin")
        sig = os.path.join(d, "sig.bin")
        with open(pub, "w") as f:
            f.write(pubpem)
        with open(dat, "wb") as f:
            f.write(data_bytes)
        with open(sig, "wb") as f:
            f.write(sig_bytes)
        r = subprocess.run(["openssl", "dgst", "-sha256", "-verify", pub, "-signature", sig, dat],
                           capture_output=True)
        return r.returncode == 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


def verify(message, pubpem):
    head, body = split_msg(message)
    hs = parse_headers(head)
    dk = next((h for h in hs if h[0] == "dkim-signature"), None)
    if not dk:
        return (False, "no DKIM-Signature header")
    tg = parse_tags(dk[1])
    c = tg.get("c", "simple/simple").split("/")
    hc, bc = c[0], (c[1] if len(c) > 1 else "simple")
    bh = base64.b64encode(hashlib.sha256(canon_body(bc, body)).digest()).decode()
    if re.sub(r"\s", "", bh) != re.sub(r"\s", "", tg["bh"]):
        return (False, "body hash mismatch")
    sd = ""
    for name in tg["h"].split(":"):
        nl = name.strip().lower()
        for h in hs:
            if h[0] == nl and h[0] != "dkim-signature":
                sd += canon_header(hc, h[0], h[1], h[2]) + "\r\n"
                break
    ev = empty_b(dk[1])
    sd += ("DKIM-Signature: " + ev) if hc == "simple" else ("dkim-signature:" + relax(ev))
    sig = base64.b64decode(re.sub(r"\s", "", tg["b"]))
    if openssl_verify(pubpem, sd.encode(), sig):
        return (True, "body hash + RSA signature valid (openssl)")
    return (False, "RSA signature invalid")


def run(ki, canon):
    r = subprocess.run([ki, os.path.join(HERE, "dkim_gen.ki"), canon],
                       capture_output=True, env={**os.environ, "KIRITO_PATH": REPO})
    out = r.stdout.decode("latin-1")
    if "SKIP" in out:
        print("[%s] SKIP (no crypto in ki build)" % canon)
        return 0
    pub = msg = None
    for line in out.split("\n"):
        if line.startswith("PUBKEY_B64:"):
            pub = base64.b64decode(line[len("PUBKEY_B64:"):]).decode("latin-1")
        elif line.startswith("MESSAGE_B64:"):
            msg = base64.b64decode(line[len("MESSAGE_B64:"):]).decode("latin-1")
    if not pub or not msg:
        print("[%s] FAIL: no signer output (%r)" % (canon, out[:200]))
        return 1
    ok, why = verify(msg, pub)
    print("[%s] %s: %s" % (canon, "INTEROP OK" if ok else "FAIL", why))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ki", default="ki")
    args = ap.parse_args()
    ki = os.path.abspath(args.ki) if os.path.exists(args.ki) else args.ki
    if not shutil.which("openssl"):
        print("SKIP: openssl not found (needed for the independent verify)")
        return 0
    rc = 0
    for canon in ("relaxed", "simple"):
        rc |= run(ki, canon)
    print("ALL DKIM INTEROP TESTS PASSED" if rc == 0 else "DKIM INTEROP FAILED")
    return rc


if __name__ == "__main__":
    sys.exit(main())
