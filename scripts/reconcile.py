"""Print the reconciliation table (Access outputs vs pandas on the source CSVs) and save it."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from reconcile import checks  # noqa: E402

result = checks(ROOT / "data/clean", ROOT / "outputs")
result.to_csv(ROOT / "outputs/reconciliation.csv", index=False)
print(result.to_string(index=False))
sys.exit(0 if result["ok"].all() else 1)
