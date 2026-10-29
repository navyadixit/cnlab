#!/usr/bin/env python3
"""Turn raw logs of one or more runs into a results table and a graph.

Usage: python3 analyze.py RESULT_DIR [RESULT_DIR ...]
Each RESULT_DIR holds: events.csv (controller), attacker.out, *_client.csv, meta.json.
Writes summary.csv and rtt.png into each folder (summary_all.csv next to them
when several folders are given).

Metrics:
  block_response_s : first BLOCKED of an attacker  minus  ATTACK START
  first_failure_s  : attacker's first failed connection minus ATTACK START
  recovery_s       : UNBLOCKED minus BLOCKED (how long the host stayed blocked)
  false_pos_blocks : BLOCKED events for any IP that is not an attacker
  rtt_*_ms         : mean RTT of normal clients before / during / after the attack
  fail_*           : failed normal-client requests before / during / after the attack
"""
import csv
import glob
import json
import os
import re
import statistics
import sys

ATTACKERS = {"10.0.0.4", "10.0.0.5"}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def read_events(folder):
    path = os.path.join(folder, "events.csv")
    rows = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            for r in csv.reader(f):
                if len(r) >= 4 and num(r[0]) is not None:
                    rows.append({"epoch": float(r[0]), "event": r[2].strip(),
                                 "ip": r[3].strip(), "detail": r[4] if len(r) > 4 else ""})
    return rows


def read_attacker(folder):
    info = {}
    path = os.path.join(folder, "attacker.out")
    if os.path.exists(path):
        text = open(path).read()
        for key, pat in (("start", r"ATTACK START\s+t=([\d.]+)"),
                         ("first_fail", r"FIRST FAILURE\s+t=([\d.]+)"),
                         ("end", r"ATTACK END\s+t=([\d.]+)")):
            m = re.search(pat, text)
            if m:
                info[key] = float(m.group(1))
    return info


def read_clients(folder):
    rows = []
    for path in sorted(glob.glob(os.path.join(folder, "*_client.csv"))):
        host = os.path.basename(path).replace("_client.csv", "")
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                t = num(r.get("epoch"))
                if t is None:
                    continue
                rows.append({"host": host, "epoch": t, "rtt": num(r.get("rtt_ms")),
                             "status": (r.get("status") or "").strip()})
    return rows


def phase(rows):
    good = [r["rtt"] for r in rows if r["status"] == "OK" and r["rtt"] is not None]
    return {"n": len(rows), "fail": len(rows) - len(good),
            "mean": statistics.mean(good) if good else None}


def analyze(folder):
    events = read_events(folder)
    att = read_attacker(folder)
    clients = read_clients(folder)
    meta = {}
    if os.path.exists(os.path.join(folder, "meta.json")):
        meta = json.load(open(os.path.join(folder, "meta.json")))

    start, end = att.get("start"), att.get("end")
    blocks = [e for e in events if e["event"] == "BLOCKED"]
    att_blocks = [e for e in blocks if e["ip"] in ATTACKERS]
    false_pos = [e for e in blocks if e["ip"] not in ATTACKERS]

    first_block = min((e["epoch"] for e in att_blocks), default=None)
    unblock = None
    if first_block is not None:
        ip = next(e["ip"] for e in att_blocks if e["epoch"] == first_block)
        unblock = min((e["epoch"] for e in events if e["event"] == "UNBLOCKED"
                       and e["ip"] == ip and e["epoch"] >= first_block), default=None)

    if start is None:   # clean run: everything counts as "before"
        before, during, after = clients, [], []
    else:
        end = end or start
        before = [r for r in clients if r["epoch"] < start]
        during = [r for r in clients if start <= r["epoch"] <= end]
        after = [r for r in clients if r["epoch"] > end]
    pb, pd, pa = phase(before), phase(during), phase(after)

    row = {
        "run": os.path.basename(os.path.normpath(folder)),
        "attack_rate": meta.get("rate", ""),
        "attacker_blocked": "yes" if first_block is not None else "no",
        "block_response_s": (first_block - start) if first_block and start else None,
        "first_failure_s": (att["first_fail"] - start) if "first_fail" in att and start else None,
        "recovery_s": (unblock - first_block) if unblock and first_block else None,
        "false_pos_blocks": len(false_pos),
        "rtt_before_ms": pb["mean"], "rtt_during_ms": pd["mean"], "rtt_after_ms": pa["mean"],
        "fail_before": pb["fail"], "fail_during": pd["fail"], "fail_after": pa["fail"],
    }
    plot(folder, clients, att, events, first_block, unblock)
    return row


def plot(folder, clients, att, events, first_block, unblock):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  (matplotlib missing: sudo apt install python3-matplotlib)")
        return
    if not clients:
        return
    ref = att.get("start") or min(r["epoch"] for r in clients)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    top = max([r["rtt"] for r in clients if r["rtt"] is not None] or [10])
    for host in sorted({r["host"] for r in clients}):
        pts = [(r["epoch"] - ref, r["rtt"]) for r in clients
               if r["host"] == host and r["status"] == "OK" and r["rtt"] is not None]
        if pts:
            ax.plot(*zip(*pts), marker=".", linewidth=1, label=f"{host} RTT")
    fails = [r["epoch"] - ref for r in clients if r["status"] != "OK"]
    if fails:
        ax.scatter(fails, [top * 1.1] * len(fails), marker="x", color="red",
                   label="failed request")
    marks = [("attack start", att.get("start"), "tab:red"),
             ("attack end", att.get("end"), "gray"),
             ("BLOCKED", first_block, "black"),
             ("UNBLOCKED", unblock, "tab:green")]
    for label, t, color in marks:
        if t:
            ax.axvline(t - ref, color=color, linestyle="--", linewidth=1)
            ax.text(t - ref, top * 1.25, label, rotation=90, va="top", ha="right",
                    fontsize=8, color=color)
    ax.set_xlabel("seconds relative to attack start" if att.get("start") else "seconds")
    ax.set_ylabel("RTT (ms)")
    ax.set_title(os.path.basename(os.path.normpath(folder)))
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(folder, "rtt.png"), dpi=130)
    plt.close(fig)


def fmt(v):
    if v is None or v == "":
        return "-"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def main():
    folders = [d for d in sys.argv[1:] if os.path.isdir(d)]
    if not folders:
        sys.exit("Usage: python3 analyze.py RESULT_DIR [RESULT_DIR ...]")
    rows = []
    for d in folders:
        row = analyze(d)
        rows.append(row)
        with open(os.path.join(d, "summary.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            w.writeheader()
            w.writerow(row)
    cols = list(rows[0])
    widths = [max(len(c), *(len(fmt(r[c])) for r in rows)) for c in cols]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(fmt(r[c]).ljust(w) for c, w in zip(cols, widths)))
    if len(rows) > 1:
        parent = os.path.dirname(os.path.abspath(folders[0]))
        with open(os.path.join(parent, "summary_all.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"\nCombined table: {os.path.join(parent, 'summary_all.csv')}")


if __name__ == "__main__":
    main()
