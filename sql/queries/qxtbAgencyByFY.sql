TRANSFORM Sum(Amount) AS Obligated
SELECT AgencyName, Sum(Amount) AS Total
FROM qryActionDetail
GROUP BY AgencyName
PIVOT 'FY' & FiscalYear IN ('FY2024', 'FY2025');
