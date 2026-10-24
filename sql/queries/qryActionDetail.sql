SELECT c.TransactionID, a.AwardKey, a.PIID, c.ModNumber, c.ActionDate,
       IIf(Month(c.ActionDate) >= 10, Year(c.ActionDate) + 1, Year(c.ActionDate)) AS FiscalYear,
       t.ActionTypeDescription, c.Amount, a.AwardType,
       r.RecipientUEI, r.RecipientName, g.AgencyID, g.AgencyName, g.SubAgencyName,
       a.NAICSCode, n.NAICSDescription
FROM ((((ContractAction AS c
    INNER JOIN Award AS a ON c.AwardKey = a.AwardKey)
    INNER JOIN Recipient AS r ON a.RecipientUEI = r.RecipientUEI)
    INNER JOIN Agency AS g ON a.AgencyID = g.AgencyID)
    INNER JOIN ActionType AS t ON c.ActionTypeCode = t.ActionTypeCode)
    LEFT JOIN NAICS AS n ON a.NAICSCode = n.NAICSCode;
