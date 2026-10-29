# How to run the experiments

Put the files of this kit into the repo (`app/` files into `app/`, `.gitignore` and
this README into the repo root). Needs the existing `server.py`, `client.py`,
`launch_clients.py` in `app/` and `controller/controller.py` (unchanged is fine).

## One-time setup (fresh Ubuntu 22.04 VM)
    bash app/setup_vm.sh
Expect `ryu-manager 4.34` and `0% dropped` at the end.

## Run one experiment (about 80 s)
    cd ~/cnlab/app
    sudo ./run_experiment.sh 50 20 test1
`50` = attacker connections/second, `20` = attack seconds, `test1` = result folder name.

| Scenario | Command |
|---|---|
| Fast attackers | `sudo ./run_experiment.sh 20 20 r20`, `... 50 20 r50`, `... 100 20 r100` |
| Slow attacker (under threshold) | `sudo ./run_experiment.sh 2 20 slow` |
| No attacker (false-positive check) | `sudo ./run_experiment.sh 0 20 clean` |

## Run everything, 3 repeats of every scenario (about 20 min)
    sudo ./run_all.sh 3

## Results
Everything lands in `~/cnlab/results/<name>/`:
`summary.csv` (metrics), `rtt.png` (graph), `events.csv` (controller), plus raw logs.
`results/summary_all.csv` combines all runs. Re-analyze any time with
`python3 app/analyze.py results/*/`.

## If something breaks
    ./app/cleanup.sh
then run again. Ryu messages are in `results/<name>/ryu.log`.

## Notes
- The controller is used as it is in `controller/controller.py`; edit its thresholds
  there and re-run, nothing else changes.
- Only one normal client runs per host (h2, h3) because the controller counts SYNs per IP:
  three requests/second from one IP already triggers a block at SYN_THRESHOLD=15, WINDOW=5.
- Attacker usage still works by hand: `h4 python3 attacker.py 10.0.0.1 50 20`.
