"""End to end: build the .mdb with Jet, read it back through 32-bit ODBC, reconcile in pandas."""

import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from reconcile import checks

ROOT = Path(__file__).resolve().parents[1]
PS32 = Path(os.environ.get("WINDIR", r"C:\Windows")) / r"SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
pytestmark = pytest.mark.skipif(not PS32.exists(), reason="needs 32-bit Windows PowerShell (Jet 4.0)")


def _ps32(script: str, *args: str) -> None:
    subprocess.run([str(PS32), "-NoProfile", "-File", str(ROOT / "scripts" / script), *args],
                   check=True, capture_output=True, text=True, timeout=600)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("mdb")
    _ps32("build_mdb.ps1", "-OutPath", str(tmp / "contracts.mdb"))
    _ps32("export_queries.ps1", "-DbPath", str(tmp / "contracts.mdb"), "-OutDir", str(tmp / "out"))
    return tmp


def test_every_reconciliation_check_passes(built):
    result = checks(ROOT / "data/clean", built / "out")
    assert len(result) == 17
    assert result["ok"].all(), result.loc[~result["ok"]].to_string()


def test_one_cent_error_is_caught(built, tmp_path):
    """The checks must be able to fail: shift one recipient total by a cent."""
    out = tmp_path / "out"
    shutil.copytree(built / "out", out)
    f = out / "qtotRecipientObligations.csv"
    q = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
    q.loc[0, "NetObligated"] = f"{float(q.loc[0, 'NetObligated']) + 0.01:.4f}"
    q.to_csv(f, index=False)
    result = checks(ROOT / "data/clean", out).set_index("check")
    assert not result.loc["totals by recipient", "ok"]
    assert result.drop("totals by recipient")["ok"].all()


def test_every_saved_select_query_was_exported(built):
    """Every non-action query in sql/queries/ was read back through ODBC."""
    exported = {p.stem for p in (built / "out").glob("q*.csv")}
    expected = {p.stem for p in (ROOT / "sql/queries").glob("*.sql")} - {"qappAgencyFYSummary"}
    assert {e.split("_FY")[0] for e in exported} == expected
