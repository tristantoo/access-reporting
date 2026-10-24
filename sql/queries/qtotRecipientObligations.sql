SELECT RecipientUEI, RecipientName,
       Count(*) AS Actions,
       Sum(Amount) AS NetObligated,
       Sum(IIf(Amount < 0, Amount, 0)) AS Deobligated,
       Min(ActionDate) AS FirstAction,
       Max(ActionDate) AS LastAction
FROM qryActionDetail
GROUP BY RecipientUEI, RecipientName
ORDER BY Sum(Amount) DESC;
