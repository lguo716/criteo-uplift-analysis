WITH outcomes AS (
    SELECT treatment, 'visit' AS outcome, visit AS positive FROM sample
    UNION ALL
    SELECT treatment, 'conversion' AS outcome, conversion AS positive FROM sample
)
SELECT outcome,
       COUNT(*) FILTER (WHERE treatment=1) AS n_treatment,
       COUNT(*) FILTER (WHERE treatment=0) AS n_control,
       SUM(positive) FILTER (WHERE treatment=1) AS positive_treatment,
       SUM(positive) FILTER (WHERE treatment=0) AS positive_control,
       AVG(positive) FILTER (WHERE treatment=1) AS rate_treatment,
       AVG(positive) FILTER (WHERE treatment=0) AS rate_control,
       AVG(positive) FILTER (WHERE treatment=1)-AVG(positive) FILTER (WHERE treatment=0) AS ate
FROM outcomes GROUP BY outcome ORDER BY outcome;
