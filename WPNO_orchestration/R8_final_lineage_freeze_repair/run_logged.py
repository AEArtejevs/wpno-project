#!/usr/bin/python3
import datetime
import json
import os
import subprocess
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codex_output")
os.makedirs(OUT, exist_ok=True)
cmd = sys.argv[1:]
started = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
proc = subprocess.run(cmd, cwd=os.getcwd(), text=True, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE)
finished = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
record = {"started_utc": started, "finished_utc": finished, "cwd": os.getcwd(),
          "argv": cmd, "returncode": proc.returncode,
          "stdout": proc.stdout, "stderr": proc.stderr}
with open(os.path.join(OUT, "COMMAND_LOG.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, sort_keys=True) + "\n")
sys.stdout.write(proc.stdout)
sys.stderr.write(proc.stderr)
raise SystemExit(proc.returncode)
