#!/usr/bin/env python3
"""Launch N normal clients at once on this host and check that none were blocked.

Usage: python3 launch_clients.py -n 2 --duration 20 --outdir ../results/test1 --prefix h2

Each client writes <outdir>/<prefix>_<i>.csv  (epoch,rtt_ms,status).
Note: all clients on one Mininet host share one IP, and the controller counts
SYNs per IP, so N clients here look like ONE busy source to the controller.
"""
import argparse
import csv
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT = os.path.join(HERE, "client.py")


def summarize(outdir, prefix):
    files = sorted(glob.glob(os.path.join(outdir, f"{prefix}_*.csv")))
    total_ok = total_fail = 0
    print(f"\n{'client':<14}{'ok':>6}{'fail':>6}{'avg rtt ms':>13}")
    for path in files:
        ok = fail = 0
        rtts = []
        with open(path) as f:
            for row in csv.DictReader(f):
                if row["status"] == "OK":
                    ok += 1
                    rtts.append(float(row["rtt_ms"]))
                else:
                    fail += 1
        avg = sum(rtts) / len(rtts) if rtts else float("nan")
        print(f"{os.path.basename(path):<14}{ok:>6}{fail:>6}{avg:>13.1f}")
        total_ok += ok
        total_fail += fail
    print(f"TOTAL ok={total_ok} fail={total_fail}")
    if total_fail == 0 and total_ok > 0:
        print("PASS: no client was blocked")
    else:
        print(f"FAIL: {total_fail} requests failed "
              "(blocked? check events.csv for BLOCKED on this IP)")


def main():
    p = argparse.ArgumentParser(description="Launch N normal clients")
    p.add_argument("-n", "--num", type=int, default=2, help="number of clients")
    p.add_argument("--server", default="10.0.0.1")
    p.add_argument("--interval", type=float, default=1.0, help="per-client interval (s)")
    p.add_argument("--duration", type=float, default=20, help="run time (s)")
    p.add_argument("--outdir", default="results")
    p.add_argument("--prefix", default="client", help="log file prefix, e.g. h2")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    print(f"Launching {args.num} clients for {args.duration:.0f}s "
          f"(aggregate ~{args.num / args.interval:.1f} req/s)", flush=True)

    procs = []
    start = time.time()
    for i in range(args.num):
        log = os.path.join(args.outdir, f"{args.prefix}_{i + 1}.csv")
        if os.path.exists(log):
            os.remove(log)
        cmd = [sys.executable, CLIENT, args.server,
               "--interval", str(args.interval), "--log", log, "--quiet"]
        procs.append(subprocess.Popen(cmd))
        time.sleep(args.interval / args.num)  # stagger so they don't fire in sync

    try:
        time.sleep(max(0, args.duration - (time.time() - start)))
    except KeyboardInterrupt:
        pass
    finally:
        for pr in procs:
            pr.terminate()
        for pr in procs:
            try:
                pr.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pr.kill()

    summarize(args.outdir, args.prefix)


if __name__ == "__main__":
    main()
