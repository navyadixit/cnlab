#!/usr/bin/env python3
"""Normal client: sends one request per interval and prints one CSV line each.

Usage: python3 client.py [server_ip] [--interval 1.0] [--count 0] [--log FILE]

Output line: epoch,rtt_ms,status
  status = OK or FAIL; rtt_ms is empty on FAIL.
  --count 0 means run until stopped (Ctrl+C or kill).
"""
import argparse
import os
import signal
import socket
import sys
import time


def open_log(path):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    f = open(path, "a", buffering=1)
    if new_file:
        f.write("epoch,rtt_ms,status\n")
    return f


def main():
    p = argparse.ArgumentParser(description="Normal TCP client")
    p.add_argument("server", nargs="?", default="10.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--interval", type=float, default=1.0, help="seconds between requests")
    p.add_argument("--count", type=int, default=0, help="number of requests (0 = forever)")
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--log", default=None, help="also append lines to this CSV file")
    p.add_argument("--quiet", action="store_true", help="don't print lines to the screen")
    args = p.parse_args()

    log = open_log(args.log) if args.log else None
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    sent = 0
    next_t = time.time()
    try:
        while args.count == 0 or sent < args.count:
            t0 = time.time()
            rtt, status = None, "FAIL"
            try:
                s = socket.create_connection((args.server, args.port),
                                             timeout=args.timeout)
                try:
                    s.sendall(b"hello")
                    reply = s.recv(1024)
                finally:
                    s.close()
                if reply:
                    rtt = (time.time() - t0) * 1000
                    status = "OK"
            except OSError:
                pass

            line = f"{t0:.3f},{rtt:.1f},{status}" if rtt is not None \
                else f"{t0:.3f},,{status}"
            if not args.quiet:
                print(line, flush=True)
            if log:
                log.write(line + "\n")

            sent += 1
            if args.count and sent >= args.count:
                break
            next_t += args.interval
            delay = next_t - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.time()  # fell behind (e.g. a timeout): don't burst
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if log:
            log.close()


if __name__ == "__main__":
    main()
