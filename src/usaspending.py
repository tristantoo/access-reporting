"""Fetch USAspending contract transactions and normalize them into relational tables.

Two stages, because the search endpoint caps pages at 100 rows and has no unique sort key
(paging over ties duplicates some rows and skips others):
  1. search_awards: paged transaction search, used only to collect awards and their attributes;
  2. award_transactions: the per-award endpoint, which pages over a stable transaction id.
The fetch script then checks the transaction count against the search endpoint's own count.
"""

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

BASE = "https://api.usaspending.gov/api/v2"
FIELDS = [
    "generated_internal_id", "Award ID", "Mod", "Action Date", "Transaction Description", "Award Type",
    "Recipient Name", "Recipient UEI", "Awarding Agency", "Awarding Sub Agency", "NAICS", "PSC",
]


def _post(path: str, body: dict, tries: int = 4) -> dict:
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except OSError as e:  # the API throws transient 500s and dropped connections
            if getattr(e, "code", 500) < 500 or attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)


def search_filters(recipient: str, start: str, end: str) -> dict:
    return {
        "recipient_search_text": [recipient],
        "award_type_codes": ["A", "B", "C", "D"],
        "time_period": [{"start_date": start, "end_date": end}],
    }


def search_rows(filters: dict) -> list[dict]:
    rows, page = [], 1
    while True:
        p = _post("/search/spending_by_transaction/", {
            "filters": filters, "fields": FIELDS, "limit": 100, "page": page,
            "sort": "Action Date", "order": "asc"})
        rows += p["results"]
        if not p["page_metadata"]["hasNext"]:
            return rows
        page += 1


def search_count(filters: dict) -> int:
    return _post("/search/spending_by_transaction_count/", {"filters": filters})["results"]["contracts"]


def award_transactions(award_key: str) -> list[dict]:
    rows, page = [], 1
    while True:
        p = _post("/transactions/", {"award_id": award_key, "limit": 100, "page": page,
                                     "sort": "action_date", "order": "asc"})
        rows += [{"award_key": award_key, **r} for r in p["results"]]
        if not p["page_metadata"]["hasNext"]:
            return rows
        page += 1


def fetch(recipient: str, start: str, end: str) -> tuple[list[dict], list[dict], int]:
    """Return (search rows, in-window transactions, the API's transaction count)."""
    filters = search_filters(recipient, start, end)
    search = search_rows(filters)
    keys = sorted({r["generated_internal_id"] for r in search})
    with ThreadPoolExecutor(4) as pool:
        txns = [t for ts in pool.map(award_transactions, keys) for t in ts
                if start <= t["action_date"] <= end]
    return search, txns, search_count(filters)


def normalize(search: list[dict], txns: list[dict]) -> dict[str, pd.DataFrame]:
    """Split API rows into Agency, Recipient, NAICS, ActionType, Award and ContractAction tables.

    Award attributes come from the award's earliest search row in the window.
    """
    s = pd.DataFrame({
        "AwardKey": [r["generated_internal_id"] for r in search],
        "PIID": [r["Award ID"] for r in search],
        "ActionDate": [r["Action Date"] for r in search],
        "AwardType": [r["Award Type"] for r in search],
        "RecipientUEI": [r["Recipient UEI"] for r in search],
        "RecipientName": [r["Recipient Name"] for r in search],
        "AgencyName": [r["Awarding Agency"] for r in search],
        "SubAgencyName": [r["Awarding Sub Agency"] for r in search],
        "NAICSCode": [(r["NAICS"] or {}).get("code") for r in search],
        "NAICSDescription": [(r["NAICS"] or {}).get("description") for r in search],
        "PSCCode": [(r["PSC"] or {}).get("code") for r in search],
        "Description": [(r["Transaction Description"] or "")[:255] for r in search],
    }).sort_values(["ActionDate", "AwardKey"], kind="stable")

    agency = (s[["AgencyName", "SubAgencyName"]].drop_duplicates()
              .sort_values(["AgencyName", "SubAgencyName"]).reset_index(drop=True))
    agency.insert(0, "AgencyID", agency.index + 1)
    s = s.merge(agency, on=["AgencyName", "SubAgencyName"])

    recipient = (s.drop_duplicates("RecipientUEI", keep="last")[["RecipientUEI", "RecipientName"]]
                 .sort_values("RecipientUEI"))
    naics = (s.dropna(subset=["NAICSCode"]).drop_duplicates("NAICSCode")[["NAICSCode", "NAICSDescription"]]
             .sort_values("NAICSCode"))
    award = (s.drop_duplicates("AwardKey")[
        ["AwardKey", "PIID", "AwardType", "RecipientUEI", "AgencyID", "NAICSCode", "PSCCode", "Description"]]
        .sort_values("AwardKey"))

    t = pd.DataFrame({
        "TransactionID": [r["id"] for r in txns],
        "AwardKey": [r["award_key"] for r in txns],
        "ModNumber": [r["modification_number"] for r in txns],
        "ActionDate": [r["action_date"] for r in txns],
        "ActionTypeCode": [r["action_type"] or "0" for r in txns],
        "ActionTypeDescription": [r["action_type_description"] or "BASE AWARD" for r in txns],
        "Amount": [round(float(r["federal_action_obligation"] or 0), 2) for r in txns],
    })
    action_type = (t.drop_duplicates("ActionTypeCode")[["ActionTypeCode", "ActionTypeDescription"]]
                   .sort_values("ActionTypeCode"))
    txn = t.drop(columns="ActionTypeDescription").sort_values("TransactionID")
    return {"Agency": agency, "Recipient": recipient, "NAICS": naics, "ActionType": action_type,
            "Award": award, "ContractAction": txn}
