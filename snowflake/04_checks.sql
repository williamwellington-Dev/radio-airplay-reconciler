-- =====================================================================
-- 04_checks.sql  -  CanCon compliance + data-quality report (same as src/checks.py)
-- =====================================================================
USE WAREHOUSE AIRPLAY_WH;
USE SCHEMA AIRPLAY.REPORTING;

CREATE OR REPLACE VIEW COMPLIANCE_REPORT AS
WITH songs AS (
    SELECT *, IS_CANCON = TRUE AS CANCON   -- unmatched songs count as non-Canadian
    FROM MATCHED_PLAYS WHERE ITEM_TYPE = 'song'
),
cancon AS (
    SELECT STATION, 'CanCon - full week' AS CHECK_NAME,
           AVG(IFF(CANCON, 1, 0)) AS SHARE, COUNT_IF(CANCON) AS CANADIAN, COUNT(*) AS TOTAL
    FROM songs GROUP BY STATION
    UNION ALL
    SELECT STATION, 'CanCon - weekday 6am-6pm',
           AVG(IFF(CANCON, 1, 0)), COUNT_IF(CANCON), COUNT(*)
    FROM songs
    WHERE DAYOFWEEKISO(PLAYED_AT) <= 5 AND HOUR(PLAYED_AT) BETWEEN 6 AND 17
    GROUP BY STATION
),
gaps AS (
    SELECT STATION, PLAYED_AT,
           DATEDIFF('second', DATEADD('second', DURATION_SEC, PLAYED_AT),
                    LEAD(PLAYED_AT) OVER (PARTITION BY STATION ORDER BY PLAYED_AT)) / 60 AS GAP_MIN,
           LEAD(PLAYED_AT) OVER (PARTITION BY STATION ORDER BY PLAYED_AT)::DATE = PLAYED_AT::DATE AS SAME_DAY
    FROM MATCHED_PLAYS
),
stations AS (SELECT DISTINCT STATION FROM MATCHED_PLAYS)
SELECT STATION, CHECK_NAME,
       TO_VARCHAR(ROUND(SHARE * 100, 1)) || '%' AS VALUE,
       IFF(SHARE >= 0.35, 'PASS', 'FAIL') AS STATUS,
       CANADIAN || ' of ' || TOTAL || ' songs (min 35%)' AS DETAIL
FROM cancon
UNION ALL
SELECT s.STATION, 'Log gaps',
       TO_VARCHAR(COUNT(g.PLAYED_AT)),
       IFF(COUNT(g.PLAYED_AT) = 0, 'PASS', 'FAIL'),
       LISTAGG(TO_VARCHAR(g.PLAYED_AT, 'DY MON DD HH24:MI') || ' (' || ROUND(g.GAP_MIN) || ' min)', '; ')
FROM stations s
LEFT JOIN gaps g ON g.STATION = s.STATION AND g.GAP_MIN > 2 AND g.SAME_DAY
GROUP BY s.STATION
UNION ALL
SELECT STATION, 'Unmatched songs',
       TO_VARCHAR(COUNT_IF(MATCH_METHOD = 'unmatched')),
       IFF(COUNT_IF(MATCH_METHOD = 'unmatched') = 0, 'PASS', 'WARN'),
       LISTAGG(DISTINCT IFF(MATCH_METHOD = 'unmatched', INITCAP(TITLE_CLEAN), NULL), ', ')
FROM songs GROUP BY STATION
UNION ALL
SELECT STATION, 'Songs missing ISRC',
       TO_VARCHAR(ROUND(AVG(IFF(ISRC IS NULL, 1, 0)) * 100, 1)) || '%',
       IFF(AVG(IFF(ISRC IS NULL, 1, 0)) < 0.10, 'PASS', 'WARN'),
       NULL
FROM songs GROUP BY STATION;

-- Expected: CXRA passes CanCon (37.2%), CXRB fails (34.7%) + 22-min gap Wed Oct 28 13:56,
--           CXRC fails (26.7%), CXRB 100% missing ISRC
SELECT * FROM COMPLIANCE_REPORT ORDER BY STATION, CHECK_NAME;
