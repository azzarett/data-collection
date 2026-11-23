SELECT COUNT(*) AS stored FROM chart_entries;
SELECT kind, period, COUNT(*) AS entries, COUNT(DISTINCT entity_key) AS entities,
       MIN(rank) AS first_rank, MAX(rank) AS last_rank, SUM(listens) AS chart_listens
FROM chart_entries GROUP BY kind, period ORDER BY kind, period;
SELECT kind, period, artist_name, track_name, listens FROM chart_entries
WHERE rank = 1 ORDER BY kind, period;
SELECT COUNT(*) AS duplicated_positions FROM (
    SELECT 1 FROM chart_entries GROUP BY kind, period, start_utc, end_utc, rank HAVING COUNT(*) > 1
);
PRAGMA integrity_check;
