-- Run with the sample view created by src.sql_checks; read-only and no extensions.
SELECT COUNT(*) AS n, COUNT(DISTINCT row_id) AS unique_rows,
       SUM(CASE WHEN treatment=0 AND exposure=1 THEN 1 ELSE 0 END) AS control_exposed,
       SUM(CASE WHEN visit=0 AND conversion=1 THEN 1 ELSE 0 END) AS conversion_without_visit
FROM sample;
