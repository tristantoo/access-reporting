"""Download Goldbelt-family contract transactions (FY2024-FY2025) and write data/clean/*.csv."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from usaspending import fetch, normalize  # noqa: E402

search, txns, api_count = fetch("Goldbelt", "2023-10-01", "2025-09-30")
(ROOT / "data/raw").mkdir(parents=True, exist_ok=True)
(ROOT / "data/raw/api.json").write_text(json.dumps({"search": search, "txns": txns}, indent=1))

# Completeness: every (award, mod) the recipient search saw must be in the per-award pull.
# The per-award pull is larger because the search matches the parent name, which FPDS
# fills on only some modifications; those extra mods belong in the award's totals.
seen = {(r["generated_internal_id"], r["Mod"]) for r in search}
got = {(t["award_key"], t["modification_number"]) for t in txns}
if missing := seen - got:
    sys.exit(f"STOP: {len(missing)} searched transactions missing from per-award pull")

tables = normalize(search, txns)
for name, df in tables.items():
    df.to_csv(ROOT / f"data/clean/{name}.csv", index=False)
    print(f"{name:15s} {len(df):6d} rows")
print(f"search: {api_count} rows ({len(seen)} distinct award+mod); per-award pull: {len(txns)} rows")
