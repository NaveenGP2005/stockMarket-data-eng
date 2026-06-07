SELECT
    current_price,
    change_amount,
    change_percent,
    day_high,
    day_low,
    day_open,
    prev_close,
    market_timestamp,
    symbol,
    fetched_at
FROM {{ source('raw', 'bronze_stock_quotes_raw') }}
