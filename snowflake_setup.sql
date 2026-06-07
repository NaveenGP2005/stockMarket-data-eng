-- =====================================================================
-- SNOWFLAKE SETUP SCRIPT FOR STOCK MARKET DATA PIPELINE
-- =====================================================================

-- 1. Create Database and Schema
CREATE DATABASE IF NOT EXISTS STOCKS_MDS;
CREATE SCHEMA IF NOT EXISTS STOCKS_MDS.COMMON;

USE DATABASE STOCKS_MDS;
USE SCHEMA COMMON;

-- 2. Create File Format for Parquet
CREATE OR REPLACE FILE FORMAT my_parquet_format
  TYPE = 'PARQUET'
  COMPRESSION = 'SNAPPY';

-- 3. Create External Stage pointing to S3 Processed Parquet directory
-- (Using credentials from your .env file)
CREATE OR REPLACE STAGE my_s3_stage
  URL = 's3://stock-naveen/processed/'
  CREDENTIALS = (
    AWS_KEY_ID = 'YOUR_AWS_ACCESS_KEY_ID' 
    AWS_SECRET_KEY = 'YOUR_AWS_SECRET_ACCESS_KEY'
  )
  FILE_FORMAT = my_parquet_format;

-- 4. Create Bronze Table with Structured Schema matching Spark Output
CREATE OR REPLACE TABLE bronze_stock_quotes_raw (
  symbol VARCHAR(10),
  current_price DOUBLE,
  change_amount DOUBLE,
  change_percent DOUBLE,
  day_high DOUBLE,
  day_low DOUBLE,
  day_open DOUBLE,
  prev_close DOUBLE,
  market_timestamp TIMESTAMP,
  fetched_at TIMESTAMP
);

-- 5. Copy the Cleaned Parquet Data from S3 into the Table
COPY INTO bronze_stock_quotes_raw
FROM (
  SELECT
    $1:symbol::varchar,
    $1:current_price::double,
    $1:change_amount::double,
    $1:change_percent::double,
    $1:day_high::double,
    $1:day_low::double,
    $1:day_open::double,
    $1:prev_close::double,
    $1:market_timestamp::timestamp,
    $1:fetched_at::timestamp
  FROM @my_s3_stage
)
FILE_FORMAT = my_parquet_format
PATTERN = '.*\\.parquet';

-- 6. Verify data load
SELECT COUNT(*) FROM bronze_stock_quotes_raw;
SELECT * FROM bronze_stock_quotes_raw LIMIT 10;
