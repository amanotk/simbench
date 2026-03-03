#!/usr/bin/env bash
set -u -o pipefail

cd /work
export PYTHONPATH="/work:/eval_shared"

status="passed"
score="1.0"

python3 -m pytest -q /eval/tests
rc=$?
if [ "$rc" -ne 0 ]; then
  status="failed"
  score="0.0"
fi

python3 - <<PY
import json
from pathlib import Path

out = {
  "status": "$status",
  "score": float("$score"),
}
Path("result.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
PY

exit 0
