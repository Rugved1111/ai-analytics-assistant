-- Staging table: raw CSV, every column as text, snake_case names.
DROP TABLE IF EXISTS stg_superstore;

CREATE TABLE stg_superstore (
    row_id        text,
    order_id      text,
    order_date    text,
    ship_date     text,
    ship_mode     text,
    customer_id   text,
    customer_name text,
    segment       text,
    country       text,
    city          text,
    state         text,
    postal_code   text,
    region        text,
    product_id    text,
    category      text,
    sub_category  text,
    product_name  text,
    sales         text,
    quantity      text,
    discount      text,
    profit        text
);