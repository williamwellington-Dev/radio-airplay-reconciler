-- =====================================================================
-- 03_transform.sql  -  clean, combine, dedupe and match (same logic as src/pipeline.py)
-- =====================================================================
USE WAREHOUSE AIRPLAY_WH;
USE SCHEMA AIRPLAY.CLEAN;

-- Same rules as clean_text() in pipeline.py:
-- lowercase/trim, drop (Radio Edit)/(Edit)/(Clean), "midnight relay, the" -> "the midnight relay",
-- featuring/feat/ft -> "feat.", squeeze extra spaces
CREATE OR REPLACE FUNCTION CLEAN_TEXT(S STRING)
RETURNS STRING
AS
$$
  REGEXP_REPLACE(
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(LOWER(TRIM(S)), '\\s*\\((radio edit|edit|clean)\\)', ''),
        '^(.*), the$', 'the \\1'),
      '\\s+(featuring|feat\\.?|ft\\.?)\\s+', ' feat. '),
    '\\s+', ' ')
$$;

-- One standard table for all three stations
CREATE OR REPLACE TABLE PLAYS AS
WITH combined AS (
    -- Station A: local time, "3:40" durations
    SELECT 'CXRA' AS STATION,
           TO_TIMESTAMP_NTZ(AIR_DATE || ' ' || AIR_TIME, 'YYYY-MM-DD HH24:MI:SS') AS PLAYED_AT,
           LOWER(TYPE) AS ITEM_TYPE,
           TITLE, ARTIST, ISRC,
           SPLIT_PART(DUR, ':', 1)::INT * 60 + SPLIT_PART(DUR, ':', 2)::INT AS DURATION_SEC
    FROM AIRPLAY.RAW.STATION_A_RAW
    UNION ALL
    -- Station B: UTC -> Toronto time, map its category names, no ISRC logged
    SELECT 'CXRB',
           CONVERT_TIMEZONE('UTC', 'America/Toronto',
                            TO_TIMESTAMP_NTZ(TS_UTC, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
           DECODE(CATEGORY, 'music', 'song', 'commercial', 'spot', 'imaging', 'liner'),
           SONG_TITLE, PERFORMER, NULL,
           DURATION_SEC::INT
    FROM AIRPLAY.RAW.STATION_B_RAW
    UNION ALL
    -- Station C: "10/26/2026 6:00:10 AM", no type column (artist present = song), "00:03:39" lengths
    SELECT 'CXRC',
           TO_TIMESTAMP_NTZ(PLAY_DATE || ' ' || START_TIME, 'MM/DD/YYYY HH12:MI:SS AM'),
           IFF(ARTIST_NAME IS NOT NULL, 'song', 'other'),
           CUT_TITLE, ARTIST_NAME, ISRC,
           SPLIT_PART(LENGTH, ':', 1)::INT * 3600 + SPLIT_PART(LENGTH, ':', 2)::INT * 60
             + SPLIT_PART(LENGTH, ':', 3)::INT
    FROM AIRPLAY.RAW.STATION_C_RAW
)
SELECT c.*,
       CLEAN_TEXT(TITLE)  AS TITLE_CLEAN,
       CLEAN_TEXT(ARTIST) AS ARTIST_CLEAN
FROM combined c
-- drop entries logged twice (same station, time and title)
QUALIFY ROW_NUMBER() OVER (PARTITION BY STATION, PLAYED_AT, TITLE ORDER BY DURATION_SEC) = 1;

CREATE OR REPLACE TABLE CATALOG AS
SELECT ISRC, TITLE, ARTIST,
       TO_BOOLEAN(IS_CANCON) AS IS_CANCON,
       LABEL,
       CLEAN_TEXT(TITLE)  AS TITLE_CLEAN,
       CLEAN_TEXT(ARTIST) AS ARTIST_CLEAN
FROM AIRPLAY.RAW.CATALOG_RAW;

-- Expected: 11,787 plays after removing 390 duplicates (12,177 raw)
SELECT COUNT(*) AS PLAYS FROM PLAYS;

-- ---------------------------------------------------------------------
-- Matching: ISRC first (exact ID), cleaned title + artist as fallback
-- ---------------------------------------------------------------------
USE SCHEMA AIRPLAY.REPORTING;

CREATE OR REPLACE TABLE MATCHED_PLAYS AS
SELECT p.*,
       COALESCE(ci.ISRC, cn.ISRC)           AS CATALOG_ISRC,
       COALESCE(ci.IS_CANCON, cn.IS_CANCON) AS IS_CANCON,
       COALESCE(ci.LABEL, cn.LABEL)         AS LABEL,
       CASE WHEN p.ITEM_TYPE <> 'song'   THEN 'not_music'
            WHEN ci.ISRC IS NOT NULL     THEN 'isrc'
            WHEN cn.ISRC IS NOT NULL     THEN 'name'
            ELSE 'unmatched' END         AS MATCH_METHOD
FROM AIRPLAY.CLEAN.PLAYS p
LEFT JOIN AIRPLAY.CLEAN.CATALOG ci
       ON p.ITEM_TYPE = 'song' AND p.ISRC = ci.ISRC
LEFT JOIN AIRPLAY.CLEAN.CATALOG cn
       ON p.ITEM_TYPE = 'song' AND ci.ISRC IS NULL
      AND p.TITLE_CLEAN = cn.TITLE_CLEAN AND p.ARTIST_CLEAN = cn.ARTIST_CLEAN;

-- Expected (isrc / name / unmatched): CXRA 1700/90/33, CXRB 0/1768/48, CXRC 1701/79/35
SELECT STATION,
       COUNT_IF(MATCH_METHOD = 'isrc')      AS BY_ISRC,
       COUNT_IF(MATCH_METHOD = 'name')      AS BY_NAME,
       COUNT_IF(MATCH_METHOD = 'unmatched') AS UNMATCHED,
       COUNT_IF(MATCH_METHOD = 'not_music') AS NOT_MUSIC
FROM MATCHED_PLAYS GROUP BY STATION ORDER BY STATION;
