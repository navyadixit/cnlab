#!/usr/bin/env python3
"""Simple multi-threaded TCP server (runs on h1)."""
import socket
import threading
import time

HOST, PORT = '0.0.0.0', 5000


def handle(conn, addr):
    try:
        conn.settimeout(5)
        data = conn.recv(1024)
        if data:
            conn.sendall(b"OK: " + data)
        print(f"[{time.strftime('%H:%M:%S')}] served {addr[0]}:{addr[1]}", flush=True)
    except Exception:
        pass
    finally:
        conn.close()


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(256)
    print(f"Server listening on {PORT}", flush=True)
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    main()
