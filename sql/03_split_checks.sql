SELECT split, treatment, visit, conversion, COUNT(*) AS n
FROM sample GROUP BY split, treatment, visit, conversion
ORDER BY split, treatment, visit, conversion;
