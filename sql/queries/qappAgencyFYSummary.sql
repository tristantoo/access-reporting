INSERT INTO AgencyFYSummary (FiscalYear, AgencyID, ActionCount, Obligated, LoadedOn)
SELECT FiscalYear, AgencyID, Count(*), Sum(Amount), Now()
FROM qryActionDetail
GROUP BY FiscalYear, AgencyID;
