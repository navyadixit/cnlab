#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 22.04 VM: Mininet, Open vSwitch, Ryu 4.34.
# Usage: bash setup_vm.sh      (asks for your sudo password; takes a few minutes)
set -e
sudo apt update
sudo apt install -y mininet openvswitch-switch git python3-pip python3-venv \
  python3-matplotlib xterm hping3 netcat-openbsd
sudo systemctl enable --now openvswitch-switch

python3 -m venv ~/ryuenv
source ~/ryuenv/bin/activate
pip install --upgrade pip
pip install "setuptools==58.2.0" wheel pbr
pip install "eventlet==0.33.3" "dnspython==2.2.1"
pip install "ryu==4.34" --no-build-isolation
# Ryu 4.34 vs newer eventlet: replace the one import that no longer exists
sed -i 's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = b""/' \
  "$VIRTUAL_ENV"/lib/python3*/site-packages/ryu/app/wsgi.py

echo
ryu-manager --version
sudo mn --test pingall
echo "Setup finished. If both lines above look right (ryu-manager 4.34, 0% dropped), you are ready."
