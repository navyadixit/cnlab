#!/usr/bin/env bash
# Run every scenario REPEATS times, then build one combined table.
# Usage: sudo ./run_all.sh [repeats]      (about 80 s per run; 5 scenarios x 3 = ~20 min)
set -u
if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo:  sudo ./run_all.sh [repeats]"; exit 1; fi
REPEATS=${1:-3}
APP_DIR=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$APP_DIR")

for rep in $(seq 1 "$REPEATS"); do
  for rate in 0 2 20 50 100; do
    case "$rate" in
      0) label=clean ;;
      2) label=slow ;;
      *) label=rate$rate ;;
    esac
    "$APP_DIR/run_experiment.sh" "$rate" 20 "${label}_run${rep}"
  done
done

echo
echo "=== all runs ==="
python3 "$APP_DIR/analyze.py" "$REPO"/results/*/
[ -n "${SUDO_USER:-}" ] && chown -R "$SUDO_USER": "$REPO" 2>/dev/null
exit 0
