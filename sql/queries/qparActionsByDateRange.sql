PARAMETERS [Start Date] DateTime, [End Date] DateTime;
SELECT TransactionID, PIID, ModNumber, ActionDate, ActionTypeDescription, Amount,
       RecipientName, AgencyName, SubAgencyName
FROM qryActionDetail
WHERE ActionDate BETWEEN [Start Date] AND [End Date]
ORDER BY ActionDate, TransactionID;
