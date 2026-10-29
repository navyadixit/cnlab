#!/usr/bin/env bash
# Reset everything after a crashed or interrupted run.  Usage: ./cleanup.sh
REPO=$(cd "$(dirname "$0")/.." && pwd)
sudo mn -c
sudo pkill -f ryu-manager
sudo pkill -f "python3 .*server.py"
sudo pkill -f "python3 .*client.py"
sudo pkill -f "python3 .*attacker.py"
sudo chown -R "$USER": "$REPO"
echo "clean."
