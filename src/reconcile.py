"""Reconcile the Access query outputs (outputs/*.csv, read through ODBC) against totals
computed independently in pandas from the source CSVs (data/clean/*.csv).

Money is compared in integer cents, so a check passes only on an exact match.
"""

from pathlib import Path

import pandas as pd

TABLES = ["Agency", "Recipient", "NAICS", "ActionType", "Award", "ContractAction"]


def load_source(clean: Path) -> dict[str, pd.DataFrame]:
    d = {t: pd.read_csv(clean / f"{t}.csv", dtype=str, keep_default_na=False) for t in TABLES}
    c = d["ContractAction"]
    c["Amount"] = c["Amount"].astype(float)
    c["ActionDate"] = pd.to_datetime(c["ActionDate"])
    c["FiscalYear"] = c["ActionDate"].dt.year + (c["ActionDate"].dt.month >= 10)
    return d


def _out(out: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(out / f"{name}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")


def _cents(s: pd.Series) -> pd.Series:
    return (pd.to_numeric(s.replace("", "0")) * 100).round().astype("int64")


def _frame_check(name: str, exp: pd.DataFrame, act: pd.DataFrame, keys: list[str], money: list[str]) -> dict:
    """Outer-join expected and actual on keys; pass only if every key and value matches."""
    for df in (exp, act):
        for k in keys:
            df[k] = df[k].astype(str)
        for m in money:
            df[m] = _cents(df[m].astype(str))
    m = exp.merge(act, on=keys, how="outer", suffixes=("_src", "_mdb"), indicator=True)
    unmatched = int((m["_merge"] != "both").sum())
    diff = max((m[f"{c}_src"] - m[f"{c}_mdb"]).abs().max() for c in money) if money else 0
    ok = unmatched == 0 and diff == 0
    return {"check": name, "source": f"{len(exp)} rows", "mdb": f"{len(act)} rows",
            "detail": f"unmatched keys {unmatched}, max diff {diff / 100:.2f}", "ok": ok}


def checks(clean: Path, out: Path) -> pd.DataFrame:
    src = load_source(clean)
    c, award, agency = src["ContractAction"], src["Award"], src["Agency"]
    detail = c.merge(award, on="AwardKey").merge(agency, on="AgencyID")
    rows = []

    counts = _out(out, "table_counts").set_index("table")["rows"].astype(int)
    for t in TABLES:
        rows.append({"check": f"rows {t}", "source": len(src[t]), "mdb": counts[t],
                     "detail": "", "ok": len(src[t]) == counts[t]})

    q = _out(out, "qryActionDetail")
    s_tot, q_tot = _cents(c["Amount"].astype(str)).sum(), _cents(q["Amount"]).sum()
    rows.append({"check": "grand total obligated", "source": f"{s_tot / 100:,.2f}", "mdb": f"{q_tot / 100:,.2f}",
                 "detail": f"{len(c)} vs {len(q)} actions", "ok": s_tot == q_tot and len(c) == len(q)})

    g = detail.groupby("RecipientUEI")["Amount"]
    exp = pd.DataFrame({"Actions": g.size(), "NetObligated": g.sum(),
                        "Deobligated": g.apply(lambda s: s[s < 0].sum())}).reset_index()
    act = _out(out, "qtotRecipientObligations")[["RecipientUEI", "Actions", "NetObligated", "Deobligated"]]
    rows.append(_frame_check("totals by recipient", exp, act, ["RecipientUEI", "Actions"],
                             ["NetObligated", "Deobligated"]))

    exp = (award.merge(agency, on="AgencyID").groupby("AgencyName")["AwardKey"].nunique()
           .rename("Awards").reset_index())
    rows.append(_frame_check("distinct awards by agency", exp, _out(out, "qtotAwardsPerAgency"),
                             ["AgencyName", "Awards"], []))

    exp = detail.pivot_table(index="AgencyName", columns="FiscalYear", values="Amount", aggfunc="sum")
    exp = exp.rename(columns=lambda fy: f"FY{fy}").reset_index()
    exp["Total"] = exp[["FY2024", "FY2025"]].sum(axis=1, min_count=1)
    exp = exp.fillna(0)
    rows.append(_frame_check("crosstab agency x FY", exp, _out(out, "qxtbAgencyByFY"),
                             ["AgencyName"], ["Total", "FY2024", "FY2025"]))

    fy25 = c[(c["ActionDate"] >= "2024-10-01") & (c["ActionDate"] <= "2025-09-30")]
    p = _out(out, "qparActionsByDateRange_FY2025")
    rows.append({"check": "parameter query FY2025", "source": f"{len(fy25)} / {fy25['Amount'].sum():,.2f}",
                 "mdb": f"{len(p)} / {_cents(p['Amount']).sum() / 100:,.2f}", "detail": "count / total",
                 "ok": set(fy25["TransactionID"]) == set(p["TransactionID"])
                 and _cents(fy25["Amount"].astype(str)).sum() == _cents(p["Amount"]).sum()})

    g = detail.groupby(["FiscalYear", "AgencyID"])["Amount"]
    exp = pd.DataFrame({"ActionCount": g.size(), "Obligated": g.sum()}).reset_index()
    act = _out(out, "AgencyFYSummary")[["FiscalYear", "AgencyID", "ActionCount", "Obligated"]]
    rows.append(_frame_check("append query snapshot", exp, act, ["FiscalYear", "AgencyID", "ActionCount"],
                             ["Obligated"]))

    exp = set(award["AwardKey"]) - set(c.loc[c["ModNumber"] == "0", "AwardKey"])
    act = set(_out(out, "qexcAwardsWithoutBaseAction")["AwardKey"])
    rows.append({"check": "exception: awards without base action", "source": len(exp), "mdb": len(act),
                 "detail": f"symmetric difference {len(exp ^ act)}", "ok": exp == act})

    integ = _out(out, "integrity")
    for _, r in integ.iterrows():
        rows.append({"check": f"integrity probe {r['probe']}", "source": "must reject",
                     "mdb": "rejected" if r["rejected"] == "True" else "ACCEPTED",
                     "detail": r["message"][:70], "ok": r["rejected"] == "True"})
    return pd.DataFrame(rows)
