#!/usr/bin/env python3
"""Normal client: one request per second. Usage: python3 client.py <server_ip> [interval]"""
import socket
import sys
import time

server = sys.argv[1] if len(sys.argv) > 1 else '10.0.0.1'
interval = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
PORT = 5000

while True:
    t0 = time.time()
    try:
        s = socket.create_connection((server, PORT), timeout=2)
        s.sendall(b"hello")
        reply = s.recv(1024)
        s.close()
        rtt = (time.time() - t0) * 1000
        print(f"[{time.strftime('%H:%M:%S')}] OK  {reply.decode()}  ({rtt:.1f} ms)", flush=True)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] FAIL {e}", flush=True)
    time.sleep(interval)
