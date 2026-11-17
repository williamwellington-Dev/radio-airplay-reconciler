-- =====================================================================
-- 02_load.sql  -  raw tables + COPY INTO from the LANDING stage
-- Upload the four files from data/raw/ to @AIRPLAY.RAW.LANDING first.
-- =====================================================================
USE WAREHOUSE AIRPLAY_WH;
USE SCHEMA AIRPLAY.RAW;

LIST @LANDING;   -- should show the 4 CSV files

-- Station A (CXRA): local time, M:SS durations
CREATE OR REPLACE TABLE STATION_A_RAW (
  AIR_DATE STRING, AIR_TIME STRING, TYPE STRING, TITLE STRING,
  ARTIST STRING, ISRC STRING, DUR STRING
);
COPY INTO STATION_A_RAW FROM @LANDING FILES = ('CXRA_asplayed.csv');

-- Station B (CXRB): UTC timestamps, own category names, no ISRC
CREATE OR REPLACE TABLE STATION_B_RAW (
  STATION STRING, TS_UTC STRING, CATEGORY STRING, SONG_TITLE STRING,
  PERFORMER STRING, DURATION_SEC STRING
);
COPY INTO STATION_B_RAW FROM @LANDING FILES = ('station_b_log.csv');

-- Station C (CXRC): US-style 12-hour dates, no song/ad column, HH:MM:SS lengths
CREATE OR REPLACE TABLE STATION_C_RAW (
  CALL_SIGN STRING, PLAY_DATE STRING, START_TIME STRING, CUT_TITLE STRING,
  ARTIST_NAME STRING, ISRC STRING, LENGTH STRING
);
COPY INTO STATION_C_RAW FROM @LANDING FILES = ('station_c_log.csv');

-- Label catalog
CREATE OR REPLACE TABLE CATALOG_RAW (
  ISRC STRING, TITLE STRING, ARTIST STRING, IS_CANCON STRING, LABEL STRING
);
COPY INTO CATALOG_RAW FROM @LANDING FILES = ('catalog.csv');

-- Expected: 4048 / 4059 / 4070 / 60
SELECT 'station_a' AS t, COUNT(*) FROM STATION_A_RAW UNION ALL
SELECT 'station_b', COUNT(*) FROM STATION_B_RAW UNION ALL
SELECT 'station_c', COUNT(*) FROM STATION_C_RAW UNION ALL
SELECT 'catalog',   COUNT(*) FROM CATALOG_RAW;
