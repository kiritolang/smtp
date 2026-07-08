#!/usr/bin/env python3
"""A minimal mock SMTP server for the TLS live tests: plaintext, STARTTLS, or implicit TLS (SMTPS),
with AUTH PLAIN/LOGIN. Binds an ephemeral 127.0.0.1 port and prints 'LISTENING <port>' when ready,
then serves connections in a loop until killed. Uses a self-signed test cert (tests/certs). Test-only.
"""
import argparse
import base64
import socket
import ssl
import sys


def _wrap(sock, cert, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    return ctx.wrap_socket(sock, server_side=True)


def handle(raw, mode, cert, key):
    st = {"conn": raw, "buf": b""}

    def send(s):
        st["conn"].sendall(s.encode("latin-1"))

    def readline():
        while b"\r\n" not in st["buf"]:
            d = st["conn"].recv(4096)
            if not d:
                return None
            st["buf"] += d
        i = st["buf"].index(b"\r\n")
        line = st["buf"][:i]
        st["buf"] = st["buf"][i + 2:]
        return line.decode("latin-1")

    def read_exact(n):
        while len(st["buf"]) < n:
            d = st["conn"].recv(4096)
            if not d:
                break
            st["buf"] += d
        st["buf"] = st["buf"][n:]

    is_tls = False
    if mode == "smtps":
        st["conn"] = _wrap(st["conn"], cert, key)
        is_tls = True

    send("220 mock.test ESMTP\r\n")
    while True:
        line = readline()
        if line is None:
            return
        cmd = line.split(" ")[0].upper()
        if cmd == "EHLO":
            caps = ["250-mock.test", "250-SIZE 10485760", "250-8BITMIME", "250-SMTPUTF8",
                    "250-ENHANCEDSTATUSCODES", "250-PIPELINING", "250-CHUNKING", "250-AUTH PLAIN LOGIN"]
            if mode == "starttls" and not is_tls:
                caps.append("250-STARTTLS")
            caps.append("250 HELP")
            send("\r\n".join(caps) + "\r\n")
        elif cmd == "HELO":
            send("250 mock.test\r\n")
        elif cmd == "STARTTLS":
            if is_tls:
                send("503 5.5.1 Already using TLS\r\n")
            else:
                send("220 2.0.0 Ready to start TLS\r\n")
                st["conn"] = _wrap(st["conn"], cert, key)
                st["buf"] = b""
                is_tls = True
        elif cmd == "AUTH":
            parts = line.split(" ")
            mech = parts[1].upper() if len(parts) > 1 else ""
            if mech == "PLAIN":
                if len(parts) < 3:
                    send("334 \r\n")
                    readline()
                send("235 2.7.0 Authentication successful\r\n")
            elif mech == "LOGIN":
                send("334 " + base64.b64encode(b"Username:").decode() + "\r\n")
                readline()
                send("334 " + base64.b64encode(b"Password:").decode() + "\r\n")
                readline()
                send("235 2.7.0 Authentication successful\r\n")
            else:
                send("535 5.7.8 Unsupported mechanism\r\n")
        elif cmd == "MAIL":
            send("250 2.1.0 Ok\r\n")
        elif cmd == "RCPT":
            send("250 2.1.5 Ok\r\n")
        elif cmd == "DATA":
            send("354 End data with <CR><LF>.<CR><LF>\r\n")
            while True:
                dl = readline()
                if dl is None or dl == ".":
                    break
            send("250 2.0.0 Ok: queued\r\n")
        elif cmd == "BDAT":
            parts = line.split(" ")
            size = int(parts[1]) if len(parts) > 1 else 0
            last = len(parts) > 2 and parts[2].upper() == "LAST"
            read_exact(size)
            send("250 2.0.0 Ok: %d octets received\r\n" % size)
            if last:
                pass
        elif cmd == "RSET":
            send("250 2.0.0 Ok\r\n")
        elif cmd == "NOOP":
            send("250 2.0.0 Ok\r\n")
        elif cmd == "QUIT":
            send("221 2.0.0 Bye\r\n")
            return
        else:
            send("500 5.5.2 Command unrecognized\r\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["plain", "starttls", "smtps"], default="starttls")
    ap.add_argument("--cert", required=True)
    ap.add_argument("--key", required=True)
    args = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    print("LISTENING %d" % srv.getsockname()[1], flush=True)

    while True:
        try:
            conn, _ = srv.accept()
        except Exception:
            break
        try:
            handle(conn, args.mode, args.cert, args.key)
        except Exception as e:
            sys.stderr.write("handler error: %r\n" % e)
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
