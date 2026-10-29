#!/usr/bin/env bash
# Run ONE full experiment: Ryu controller + Mininet topology + server +
# normal clients + attacker, then analyze the logs.
#
# Usage: sudo ./run_experiment.sh [rate] [attack_seconds] [name]
#   rate 50  -> attacker at 50 connections/s        (default)
#   rate 0   -> no attacker (false-positive check: nobody should be blocked)
#   rate 2   -> "slow" attacker, just under the SYN threshold
# Results go to <repo>/results/<name>/
set -u
if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo:  sudo ./run_experiment.sh [rate] [attack_seconds] [name]"; exit 1
fi

RATE=${1:-50}
ATTACK=${2:-20}
NAME=${3:-rate${RATE}_$(date +%H%M%S)}
BASELINE=${BASELINE:-10}
if [ "$RATE" = "0" ]; then RECOVERY=${RECOVERY:-5}; else RECOVERY=${RECOVERY:-40}; fi

APP_DIR=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$APP_DIR")
CONTROLLER="$REPO/controller/controller.py"
OUT="$REPO/results/$NAME"
REAL_USER=${SUDO_USER:-root}
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
RYU=${RYU:-$REAL_HOME/ryuenv/bin/ryu-manager}

[ -x "$RYU" ]        || { echo "Ryu not found at $RYU (run setup_vm.sh first)"; exit 1; }
[ -f "$CONTROLLER" ] || { echo "Controller not found: $CONTROLLER"; exit 1; }

RYU_PID=""
cleanup() {
  [ -n "$RYU_PID" ] && kill "$RYU_PID" 2>/dev/null
  mn -c >/dev/null 2>&1
  [ -n "${SUDO_USER:-}" ] && chown -R "$SUDO_USER": "$REPO" 2>/dev/null
  return 0
}
trap cleanup EXIT

echo "=== experiment '$NAME': rate=$RATE attack=${ATTACK}s baseline=${BASELINE}s recovery=${RECOVERY}s ==="
mn -c >/dev/null 2>&1
pkill -f ryu-manager 2>/dev/null
sleep 1
rm -rf "$OUT"; mkdir -p "$OUT"

# Start Ryu with the result folder as working dir, so events.csv lands there
( cd "$OUT" && exec "$RYU" "$CONTROLLER" > ryu.log 2>&1 ) &
RYU_PID=$!

READY=0
for _ in $(seq 1 30); do
  if ss -ltn 2>/dev/null | grep -q ':6653 '; then READY=1; break; fi
  if ! kill -0 "$RYU_PID" 2>/dev/null; then
    echo "Ryu crashed on startup:"; tail -20 "$OUT/ryu.log"; exit 1
  fi
  sleep 1
done
[ "$READY" = 1 ] || { echo "Ryu never started listening on 6653"; tail -20 "$OUT/ryu.log"; exit 1; }

python3 "$APP_DIR/run_experiment.py" --outdir "$OUT" --rate "$RATE" \
  --attack-time "$ATTACK" --baseline "$BASELINE" --recovery "$RECOVERY"
STATUS=$?

kill "$RYU_PID" 2>/dev/null; RYU_PID=""
sleep 1
if [ "$STATUS" -ne 0 ]; then echo "Experiment failed (status $STATUS). See $OUT/ryu.log"; exit "$STATUS"; fi

echo
python3 "$APP_DIR/analyze.py" "$OUT"
echo
echo "Results saved in $OUT  (summary.csv, rtt.png, events.csv, logs)"
