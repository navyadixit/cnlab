#!/usr/bin/env python3
"""Abnormal traffic generator: rapid TCP connections to the server.

Usage: python3 attacker.py [server_ip] [connections_per_second] [duration_s]
                           [--port 5000] [--timeout 0.5] [--log FILE]

Prints these lines (analyze.py parses them):
  ATTACK START t=<epoch>
  FIRST FAILURE t=<epoch> ...    first refused/timed-out connection = host blocked
  ATTACK END t=<epoch>
  DONE ok=<n> fail=<n> actual_rate=<x>/s

Slow attacker: use a rate just under the controller threshold, e.g. rate 2
(SYN_THRESHOLD 15 in a 5 s window is about 3 connections/s).
"""
import argparse
import os
import signal
import socket
import time

stop = False


def on_term(*_):
    global stop
    stop = True


def main():
    p = argparse.ArgumentParser(description="Attack traffic generator")
    p.add_argument("server", nargs="?", default="10.0.0.1")
    p.add_argument("rate", nargs="?", type=float, default=50, help="connections/second")
    p.add_argument("duration", nargs="?", type=float, default=20, help="seconds")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--timeout", type=float, default=0.5)
    p.add_argument("--log", default=None, help="write epoch,status per attempt")
    args = p.parse_args()

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    log = None
    if args.log:
        folder = os.path.dirname(args.log)
        if folder:
            os.makedirs(folder, exist_ok=True)
        log = open(args.log, "w", buffering=1)
        log.write("epoch,status\n")

    start = time.time()
    print(f"ATTACK START t={start:.3f}", flush=True)
    ok = fail = 0
    first_fail = None
    period = 1.0 / args.rate
    next_t = start

    while not stop and time.time() - start < args.duration:
        t0 = time.time()
        try:
            s = socket.create_connection((args.server, args.port), timeout=args.timeout)
            s.sendall(b"x")
            s.close()
            status = "OK"
            ok += 1
        except OSError:
            status = "FAIL"
            fail += 1
            if first_fail is None:
                first_fail = t0
                print(f"FIRST FAILURE t={first_fail:.3f}  "
                      f"(~{first_fail - start:.2f}s after start, after {ok} successes)",
                      flush=True)
        if log:
            log.write(f"{t0:.3f},{status}\n")

        next_t += period
        delay = next_t - time.time()
        if delay > 0:
            time.sleep(delay)
        else:
            next_t = time.time()  # behind schedule (slow connects): don't burst

    end = time.time()
    print(f"ATTACK END t={end:.3f}", flush=True)
    actual = (ok + fail) / max(end - start, 1e-9)
    print(f"DONE ok={ok} fail={fail} actual_rate={actual:.1f}/s", flush=True)
    if log:
        log.close()


if __name__ == "__main__":
    main()
