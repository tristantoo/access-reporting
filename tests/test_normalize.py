from usaspending import normalize


def _search(award, mod, date, agency="Dept A", sub="Office 1", uei="UEI1", name="CO LLC", naics="541611"):
    return {"generated_internal_id": award, "Award ID": award[-4:], "Mod": mod, "Action Date": date,
            "Transaction Description": f"desc {mod}", "Award Type": "DELIVERY ORDER",
            "Recipient Name": name, "Recipient UEI": uei, "Awarding Agency": agency,
            "Awarding Sub Agency": sub, "NAICS": {"code": naics, "description": "CONSULTING"},
            "PSC": {"code": "R408"}}


def _txn(award, mod, date, amount, action_type=None):
    return {"award_key": award, "id": f"TX_{award}_{mod}", "modification_number": mod, "action_date": date,
            "action_type": action_type, "action_type_description": action_type and "EXERCISE AN OPTION",
            "federal_action_obligation": amount}


SEARCH = [
    _search("AWD_0002", "P00001", "2024-03-01", name="CO LLC (RENAMED)"),
    _search("AWD_0002", "0", "2023-11-01"),
    _search("AWD_0001", "0", "2024-01-01", agency="Dept B", sub="Office 9", uei="UEI2", naics=None),
]
TXNS = [_txn("AWD_0002", "0", "2023-11-01", 100.0), _txn("AWD_0002", "P00001", "2024-03-01", -25.5, "G"),
        _txn("AWD_0001", "0", "2024-01-01", 10.004)]


def test_award_attributes_come_from_earliest_row():
    award = normalize(SEARCH, TXNS)["Award"].set_index("AwardKey")
    assert award.loc["AWD_0002", "Description"] == "desc 0"
    assert len(award) == 2


def test_agency_surrogate_keys_are_sorted_and_referenced():
    t = normalize(SEARCH, TXNS)
    assert t["Agency"]["AgencyID"].tolist() == [1, 2]
    assert set(t["Award"]["AgencyID"]) <= set(t["Agency"]["AgencyID"])


def test_recipient_takes_latest_name_and_missing_naics_is_null():
    t = normalize([dict(r, NAICS=None) if r["Award ID"] == "0001" else r for r in SEARCH], TXNS)
    assert t["Recipient"].set_index("RecipientUEI").loc["UEI1", "RecipientName"] == "CO LLC (RENAMED)"
    assert t["Award"].set_index("AwardKey")["NAICSCode"].isna().sum() == 1


def test_base_award_gets_action_type_zero_and_amounts_round_to_cents():
    t = normalize(SEARCH, TXNS)
    assert set(t["ActionType"]["ActionTypeCode"]) == {"0", "G"}
    assert t["ContractAction"]["Amount"].tolist() == [10.0, 100.0, -25.5]
