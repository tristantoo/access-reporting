SELECT AgencyName, Count(*) AS Awards
FROM (SELECT DISTINCT g.AgencyName, a.AwardKey
      FROM Award AS a INNER JOIN Agency AS g ON a.AgencyID = g.AgencyID) AS d
GROUP BY AgencyName
ORDER BY Count(*) DESC;
