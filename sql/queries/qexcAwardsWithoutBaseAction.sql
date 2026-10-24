SELECT a.AwardKey, a.PIID, a.AwardType, a.RecipientUEI, a.Description
FROM Award AS a
    LEFT JOIN (SELECT AwardKey FROM ContractAction WHERE ModNumber = '0') AS b
    ON a.AwardKey = b.AwardKey
WHERE b.AwardKey IS NULL
ORDER BY a.AwardKey;
