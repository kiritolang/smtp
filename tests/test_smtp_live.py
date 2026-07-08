#!/usr/bin/env python3
"""Live TLS integration harness. For each of STARTTLS and implicit SMTPS: start the Python mock SMTP
server on an ephemeral port, run the Kirito client (tests/live_client.ki) against it over real TLS, and
require it to print 'ALL OK'. If the ki build has no TLS the client prints 'SKIP' and the mode is
skipped (not failed). Usage: python3 tests/test_smtp_live.py --ki /path/to/ki
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CERT = os.path.join(HERE, "certs", "test.crt")
KEY = os.path.join(HERE, "certs", "test.key")


def run_mode(ki, mode):
    server = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "mock_smtp_server.py"), "--mode", mode, "--cert", CERT, "--key", KEY],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    port = None
    for _ in range(200):
        line = server.stdout.readline()
        if not line:
            break
        if line.startswith("LISTENING"):
            port = int(line.split()[1])
            break
    if port is None:
        server.kill()
        print("[%s] FAIL: mock server did not start" % mode)
        return 1
    env = dict(os.environ)
    env["KIRITO_PATH"] = REPO
    try:
        client = subprocess.run(
            [ki, os.path.join(HERE, "live_client.ki"), "127.0.0.1", str(port), mode],
            capture_output=True, text=True, timeout=60, env=env)
    except subprocess.TimeoutExpired:
        server.kill()
        print("[%s] FAIL: client timed out" % mode)
        return 1
    finally:
        server.kill()
    out = (client.stdout or "").strip()
    err = (client.stderr or "").strip()
    if "SKIP" in out:
        print("[%s] SKIP (%s)" % (mode, out))
        return 0
    if "ALL OK" in out and client.returncode == 0:
        print("[%s] PASS: %s" % (mode, out))
        return 0
    print("[%s] FAIL: rc=%s out=%r err=%r" % (mode, client.returncode, out, err))
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ki", default="ki")
    args = ap.parse_args()
    ki = os.path.abspath(args.ki) if os.path.exists(args.ki) else args.ki
    rc = 0
    for mode in ("starttls", "smtps"):
        rc |= run_mode(ki, mode)
    print("ALL TLS LIVE TESTS PASSED" if rc == 0 else "TLS LIVE TESTS FAILED")
    return rc


if __name__ == "__main__":
    sys.exit(main())
