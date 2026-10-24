# access-reporting

A Microsoft Access reporting database over public federal contract data: every FY2024 and FY2025 contract action (obligation, modification, deobligation) on awards that USAspending.gov links to Goldbelt-family companies. The data comes to 2,139 actions on 715 awards from 14 agencies, $803.6M net obligated.

The database `db/contracts.mdb` contains:

- **Six related tables.** Agency, Recipient, NAICS and ActionType are lookups. Award and ContractAction hold the facts. Primary keys and foreign keys are declared in the file, so the engine enforces referential integrity.
- **A snapshot table**, AgencyFYSummary, filled by an append query.
- **Seven saved queries:**

| Query | Kind | What it answers |
|---|---|---|
| `qryActionDetail` | select (5-table join) | one row per action, with names and fiscal year; the base the other queries build on |
| `qtotRecipientObligations` | totals | actions, net obligated and deobligated per company |
| `qtotAwardsPerAgency` | totals (distinct count) | awards per agency, using Jet's workaround for its missing `COUNT(DISTINCT)` |
| `qparActionsByDateRange` | parameter | actions between `[Start Date]` and `[End Date]`, which Access prompts for |
| `qxtbAgencyByFY` | crosstab | agencies down the side, fiscal years across the top |
| `qappAgencyFYSummary` | append (action) | writes agency by FY totals into the snapshot table |
| `qexcAwardsWithoutBaseAction` | unmatched / exception | 330 awards with no base action (mod 0) in the window: their totals are modifications only |

The SQL is in `sql/schema.sql` and `sql/queries/*.sql`. The query name is the file name.

## Reconciliation

`scripts/export_queries.ps1` reads the finished file back through the 32-bit ODBC driver ("Microsoft Access Driver (*.mdb)"). This is a different path from the one used to build it. The script writes every query result to `outputs/`. Then `scripts/reconcile.py` recomputes each number in pandas from the source CSVs and compares the two in integer cents.

All 17 checks pass:
- the row count of each table
- the grand total ($803,567,005.99 in both)
- the totals per recipient
- distinct awards per agency
- every crosstab cell
- the parameter query for FY2025 (1,090 actions)
- the append snapshot
- the exception list

Four integrity probes check that the engine refuses bad writes:
- an orphan action
- deleting an award that has actions
- a duplicate primary key
- a NULL in a required field

The engine rejects all four. A test also adds one cent to one total and confirms the check fails.

## Reproduce (Windows)

```powershell
uv sync
uv run python scripts/fetch_data.py      # optional: re-pull from api.usaspending.gov (no key); data/clean/ is committed
.\scripts\build_mdb.ps1                  # -> db/contracts.mdb
.\scripts\export_queries.ps1             # -> outputs/*.csv via 32-bit ODBC
uv run python scripts/reconcile.py       # prints the check table, exits 1 on any mismatch
uv run pytest -q                         # builds a fresh .mdb in a temp dir and runs all of the above
```

The committed CSVs were pulled on 2026-10-23. Federal agencies revise records after the fact, so a re-pull can change the numbers.

## How it was built, and what is not here

Microsoft Access is not installed on the build machine. The file is built with the **Jet 4.0 database engine**, which ships with Windows. Jet is the engine Access itself uses for `.mdb` files. The steps are:
1. ADOX creates the file in Access 2000-2003 format.
2. ADO runs the Jet DDL and loads the rows with parameterized inserts.
3. DAO saves the queries as QueryDefs, the native Access query object.

Jet and DAO are 32-bit only, so the scripts relaunch themselves under 32-bit Windows PowerShell. Nothing is installed and no settings are changed.

The same `.mdb` should open in Access 2000 through Microsoft 365. Newer versions may offer to convert it to `.accdb`. However, it has **not been opened in the Access UI**. Two things are therefore unverified:
- that the queries appear in the Navigation Pane
- that the relationships appear in the Relationships window

The engine-level behavior is verified by the tests.

**Forms and reports are not included.** They are Access UI objects and need Access to build.

### Adding one form and one report once Access is available

1. **Open and check.**
   - Open `db/contracts.mdb`.
   - Go to Database Tools > Relationships and click All Relationships. You should see six lines with the "1" and "∞" ends. Double-click one and confirm that Enforce Referential Integrity is ticked.
2. **Form: Award browser with its actions.**
   - Select the `Award` table and choose Create > Form.
   - Access adds a subform for `ContractAction` automatically, because the relationship exists.
   - In Design View, replace the AgencyID text box with a combo box (row source `SELECT AgencyID, AgencyName & ' / ' & SubAgencyName FROM Agency`, column widths `0";3"`), so users pick a name, not a number.
   - Add a text box to the subform footer with the control source `=Sum([Amount])`, which gives the award total.
3. **Report: Obligations by agency and fiscal year.**
   - Choose Create > Report Wizard and pick `qryActionDetail`.
   - Select the fields AgencyName, FiscalYear, PIID, ActionDate and Amount.
   - Group by AgencyName, then FiscalYear. Under Summary Options, tick Sum for Amount.
   - Pick a stepped layout.
   - In Design View, set the report's Record Source to `qparActionsByDateRange` so the report asks for a date range when it opens.
   - Check that the grand total equals the qxtbAgencyByFY Total column for the same range.

## Layout

```
sql/schema.sql            tables, keys, relationships (Jet DDL)
sql/queries/*.sql         saved queries
scripts/fetch_data.py     USAspending API -> data/raw (ignored) -> data/clean/*.csv
scripts/build_mdb.ps1     CSV -> db/contracts.mdb (ADOX + ADO + DAO, 32-bit)
scripts/export_queries.ps1  .mdb -> outputs/*.csv through 32-bit ODBC, plus integrity probes
scripts/reconcile.py      pandas vs Access, cent-exact
src/                      fetch/normalize and reconciliation logic
tests/                    pytest (unit + end-to-end build)
```

### Data notes

- **The search undercounts.** USAspending's recipient search matches on the parent company name, and the federal procurement system (FPDS) fills that field on only some modifications. So the search returns 2,062 of the 2,139 in-window actions on these awards. The fetch therefore uses the search only to find the awards. It then pulls each award's actions from the per-award endpoint and stops if any searched action is missing.
- **Award attributes** (agency, NAICS, description) come from the award's earliest action in the window.
- **Fiscal year** runs October to September (FY2025 = 2024-10-01 to 2025-09-30).

## Authorship

Built with AI coding assistance (Claude Code). I set the scope and questions and reviewed the methods, code and results.
