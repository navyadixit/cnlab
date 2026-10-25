#!/usr/bin/env python3
"""Abnormal traffic generator: many rapid TCP connections.
Usage: python3 attacker.py <server_ip> [connections_per_second] [duration_s]
Logs the time the attack starts and the time connections begin failing (= blocked).
"""
import socket
import sys
import time

server = sys.argv[1] if len(sys.argv) > 1 else '10.0.0.1'
rate = float(sys.argv[2]) if len(sys.argv) > 2 else 50
duration = float(sys.argv[3]) if len(sys.argv) > 3 else 60
PORT = 5000

start = time.time()
print(f"ATTACK START  t={start:.3f}", flush=True)
ok = fail = 0
first_fail = None
while time.time() - start < duration:
    try:
        s = socket.create_connection((server, PORT), timeout=1)
        s.sendall(b"x")
        s.close()
        ok += 1
    except Exception:
        fail += 1
        if first_fail is None:
            first_fail = time.time()
            print(f"FIRST FAILURE t={first_fail:.3f}  "
                  f"(~{first_fail - start:.2f}s after start, after {ok} successes)", flush=True)
    time.sleep(1.0 / rate)
print(f"DONE ok={ok} fail={fail}", flush=True)
