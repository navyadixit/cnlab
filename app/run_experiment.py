#!/usr/bin/env python3
"""Run one experiment inside Mininet (called by run_experiment.sh, needs root).

Timeline: start server + normal clients -> BASELINE seconds of normal traffic ->
attacker runs for ATTACK seconds -> RECOVERY seconds of waiting (so the block
timer expires and recovery is captured) -> stop everything.
rate 0 means no attacker (false-positive check: nobody should be blocked).

Writes into --outdir: server.log, h2_client.csv, h3_client.csv, attacker.out,
attacker_attempts.csv, meta.json (events.csv and ryu.log come from the controller).
"""
import argparse
import json
import os
import subprocess
import sys
import time

from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController

HERE = os.path.dirname(os.path.abspath(__file__))


def launch(host, cmd, out, logname):
    f = open(os.path.join(out, logname), "w")
    proc = host.popen(cmd, stdout=f, stderr=subprocess.STDOUT)
    return proc, f


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", required=True)
    p.add_argument("--rate", type=float, default=50)
    p.add_argument("--attack-time", type=float, default=20)
    p.add_argument("--baseline", type=float, default=10)
    p.add_argument("--recovery", type=float, default=40)
    p.add_argument("--client-interval", type=float, default=1.0)
    args = p.parse_args()

    out = os.path.abspath(args.outdir)
    os.makedirs(out, exist_ok=True)
    setLogLevel("warning")

    net = Mininet(controller=None, switch=OVSKernelSwitch, autoSetMacs=True)
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    h1 = net.addHost("h1", ip="10.0.0.1/24")  # server
    h2 = net.addHost("h2", ip="10.0.0.2/24")  # normal client
    h3 = net.addHost("h3", ip="10.0.0.3/24")  # normal client
    h4 = net.addHost("h4", ip="10.0.0.4/24")  # attacker
    for h in (h1, h2, h3, h4):
        net.addLink(h, s1)

    procs, files = [], []
    meta = {"rate": args.rate, "attack_seconds": args.attack_time,
            "baseline": args.baseline, "recovery": args.recovery}
    try:
        net.start()
        if hasattr(net, "waitConnected"):
            if not net.waitConnected(timeout=20):
                sys.exit("Switch never connected to the controller (is Ryu running?)")
        else:
            time.sleep(4)

        drops = 100
        for _ in range(3):  # warm-up so the switch learns every MAC
            drops = net.pingAll()
            if drops == 0:
                break
            time.sleep(2)
        print(f"warm-up ping: {drops:.0f}% dropped", flush=True)

        srv, f = launch(h1, ["python3", os.path.join(HERE, "server.py"),
                             "--log", os.path.join(out, "server.log"), "--quiet"],
                        out, "server.out")
        procs.append(srv); files.append(f)
        time.sleep(1)

        for host, name in ((h2, "h2"), (h3, "h3")):
            c, f = launch(host, ["python3", os.path.join(HERE, "client.py"), "10.0.0.1",
                                 "--interval", str(args.client_interval),
                                 "--log", os.path.join(out, f"{name}_client.csv"),
                                 "--quiet"], out, f"{name}_client.out")
            procs.append(c); files.append(f)

        meta["t_start"] = time.time()
        print(f"baseline traffic for {args.baseline:.0f}s ...", flush=True)
        time.sleep(args.baseline)

        meta["t_attack_launch"] = time.time()
        if args.rate > 0:
            print(f"attacker: {args.rate:g} conn/s for {args.attack_time:.0f}s ...", flush=True)
            att, f = launch(h4, ["python3", os.path.join(HERE, "attacker.py"), "10.0.0.1",
                                 str(args.rate), str(args.attack_time),
                                 "--log", os.path.join(out, "attacker_attempts.csv")],
                            out, "attacker.out")
            files.append(f)
            att.wait()
        else:
            print(f"no attacker (clean run) for {args.attack_time:.0f}s ...", flush=True)
            time.sleep(args.attack_time)

        print(f"waiting {args.recovery:.0f}s for the block to expire ...", flush=True)
        time.sleep(args.recovery)
        meta["t_end"] = time.time()
    finally:
        for pr in procs:
            try:
                stop(pr)
            except Exception:
                pass
        for f in files:
            f.close()
        with open(os.path.join(out, "meta.json"), "w") as mf:
            json.dump(meta, mf, indent=2)
        net.stop()


if __name__ == "__main__":
    main()
