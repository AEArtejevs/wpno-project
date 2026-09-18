#!/usr/bin/python3
import datetime, json, os, subprocess, sys

OUT = "/home/ubuntu/project/WPNO_orchestration/R8_final_delta_closure/codex_output"
root = sys.argv[1]
cmd = sys.argv[2:]
started = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
p = subprocess.run(cmd, cwd=root)
row = {"command": cmd, "root": root, "exit_status": p.returncode, "utc": started}
with open(os.path.join(OUT, "COMMAND_LOG.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps(row, separators=(",", ":")) + "\n")
raise SystemExit(p.returncode)
