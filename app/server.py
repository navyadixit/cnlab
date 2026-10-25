#!/usr/bin/env python3
"""Multi-threaded TCP server (runs on h1) with per-connection logging.

Usage: python3 server.py [--port 5000] [--log results/server.log] [--quiet]

Log format (CSV): epoch,client_ip,client_port,bytes,status
  bytes  = bytes received from the client
  status = OK (data received and answered), EMPTY (no data), ERROR (timeout/reset)
"""
import argparse
import os
import signal
import socket
import sys
import threading
import time

log_lock = threading.Lock()
log_file = None
total = 0


def open_log(path):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    f = open(path, "a", buffering=1)  # line buffered
    if new_file:
        f.write("epoch,client_ip,client_port,bytes,status\n")
    return f


def log_connection(addr, nbytes, status):
    global total
    line = f"{time.time():.3f},{addr[0]},{addr[1]},{nbytes},{status}\n"
    with log_lock:
        total += 1
        log_file.write(line)


def handle(conn, addr, quiet):
    nbytes, status = 0, "OK"
    try:
        conn.settimeout(5)
        data = conn.recv(1024)
        nbytes = len(data)
        if data:
            conn.sendall(b"OK: " + data)
        else:
            status = "EMPTY"
    except Exception:
        status = "ERROR"
    finally:
        conn.close()
        log_connection(addr, nbytes, status)
        if not quiet:
            print(f"[{time.strftime('%H:%M:%S')}] {status} {addr[0]}:{addr[1]} "
                  f"{nbytes}B", flush=True)


def main():
    global log_file
    p = argparse.ArgumentParser(description="TCP server with logging")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--log", default="server.log", help="CSV log path")
    p.add_argument("--quiet", action="store_true", help="don't print each connection")
    args = p.parse_args()

    log_file = open_log(args.log)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((args.host, args.port))
    s.listen(256)
    print(f"Server listening on {args.port}, logging to {args.log}", flush=True)

    # make `kill` (SIGTERM) shut down as cleanly as Ctrl+C
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    try:
        while True:
            try:
                conn, addr = s.accept()
            except OSError:
                time.sleep(0.05)  # e.g. too many open files: back off, keep serving
                continue
            threading.Thread(target=handle, args=(conn, addr, args.quiet),
                             daemon=True).start()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        s.close()
        with log_lock:
            log_file.close()
        print(f"\nServer stopped. {total} connections logged.", flush=True)


if __name__ == "__main__":
    main()
