-- =====================================================================
-- 01_setup.sql  -  warehouse, database, schemas, file format, stage
-- Run once, as ACCOUNTADMIN, in a Snowsight SQL worksheet.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

-- Small warehouse that suspends itself after 60s idle (saves trial credits)
CREATE WAREHOUSE IF NOT EXISTS AIRPLAY_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS AIRPLAY;
CREATE SCHEMA IF NOT EXISTS AIRPLAY.RAW;      -- files exactly as the stations sent them
CREATE SCHEMA IF NOT EXISTS AIRPLAY.CLEAN;    -- one standard play table
CREATE SCHEMA IF NOT EXISTS AIRPLAY.REPORTING; -- matching + compliance results

USE WAREHOUSE AIRPLAY_WH;
USE SCHEMA AIRPLAY.RAW;

-- Read the CSVs as text; all type conversion happens in 03_transform.sql
CREATE OR REPLACE FILE FORMAT CSV_HEADER
  TYPE = CSV
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  EMPTY_FIELD_AS_NULL = TRUE
  TRIM_SPACE = FALSE;            -- keep the messy spacing; cleaning is part of the pipeline

-- Internal stage to upload the four CSV files into (Snowsight: Data > Add Data > Load files into a Stage)
CREATE OR REPLACE STAGE LANDING
  FILE_FORMAT = CSV_HEADER
  DIRECTORY = (ENABLE = TRUE);

-- Make sure Cortex AI can reach every model (default for new accounts, harmless to repeat)
ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';
