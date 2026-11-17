-- =====================================================================
-- 05_fuzzy_match.sql  -  suggest catalog matches for unmatched songs
-- For each unmatched song, find the 3 closest catalog tracks using Snowflake's
-- built-in JAROWINKLER_SIMILARITY (0-100), then flag the best one as a
-- "likely match" when it scores high enough. A human approves the result.
-- =====================================================================
USE WAREHOUSE AIRPLAY_WH;
USE SCHEMA AIRPLAY.REPORTING;

-- 1) Shortlist: 3 closest catalog tracks per unmatched song
CREATE OR REPLACE TABLE UNMATCHED_CANDIDATES AS
WITH unmatched AS (
    SELECT TITLE_CLEAN, ARTIST_CLEAN,
           COUNT(*) AS PLAYS,
           LISTAGG(DISTINCT STATION, ', ') WITHIN GROUP (ORDER BY STATION) AS STATIONS
    FROM MATCHED_PLAYS
    WHERE MATCH_METHOD = 'unmatched'
    GROUP BY TITLE_CLEAN, ARTIST_CLEAN
)
SELECT u.TITLE_CLEAN, u.ARTIST_CLEAN, u.PLAYS, u.STATIONS,
       c.ISRC, c.TITLE AS CAT_TITLE, c.ARTIST AS CAT_ARTIST,
       JAROWINKLER_SIMILARITY(u.TITLE_CLEAN || ' by ' || u.ARTIST_CLEAN,
                              c.TITLE_CLEAN || ' by ' || c.ARTIST_CLEAN) AS SIMILARITY,
       ROW_NUMBER() OVER (PARTITION BY u.TITLE_CLEAN, u.ARTIST_CLEAN
                          ORDER BY JAROWINKLER_SIMILARITY(u.TITLE_CLEAN || ' by ' || u.ARTIST_CLEAN,
                                   c.TITLE_CLEAN || ' by ' || c.ARTIST_CLEAN) DESC) AS RANK_NO
FROM unmatched u CROSS JOIN AIRPLAY.CLEAN.CATALOG c
QUALIFY RANK_NO <= 3;

-- 2) One review row per unmatched song: best candidate + a suggested action
CREATE OR REPLACE VIEW MATCH_SUGGESTIONS AS
SELECT TITLE_CLEAN AS PLAYED_TITLE, ARTIST_CLEAN AS PLAYED_ARTIST, PLAYS, STATIONS,
       CAT_TITLE AS BEST_CATALOG_TITLE, CAT_ARTIST AS BEST_CATALOG_ARTIST, ISRC AS SUGGESTED_ISRC,
       SIMILARITY,
       CASE WHEN SIMILARITY >= 90 THEN 'likely match - approve'
            WHEN SIMILARITY >= 80 THEN 'possible match - review'
            ELSE 'probably not in catalog' END AS SUGGESTION
FROM UNMATCHED_CANDIDATES
WHERE RANK_NO = 1;

SELECT * FROM MATCH_SUGGESTIONS ORDER BY SIMILARITY DESC, PLAYS DESC;
