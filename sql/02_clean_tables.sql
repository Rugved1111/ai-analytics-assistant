-- Build clean, typed, normalized tables from stg_superstore.
-- Re-runnable: drops and rebuilds the 4 tables. Staging is not touched.

\set ON_ERROR_STOP on

BEGIN;

DROP TABLE IF EXISTS order_lines;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

-- One row per customer. customer_id is unique (checked: 0 IDs with 2 names).
CREATE TABLE customers (
    customer_id   text PRIMARY KEY,
    customer_name text NOT NULL,
    segment       text NOT NULL
);

-- One row per real product. product_id is NOT unique in the source
-- (32 IDs carry 2 different products), so we add a surrogate key.
CREATE TABLE products (
    product_key   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id    text NOT NULL,
    product_name  text NOT NULL,
    category      text NOT NULL,
    sub_category  text NOT NULL,
    UNIQUE (product_id, product_name)
);

-- One row per order. The delivery address lives here, not on customers
-- (780 of 793 customers had orders shipped to more than one city).
CREATE TABLE orders (
    order_id    text PRIMARY KEY,
    customer_id text NOT NULL REFERENCES customers (customer_id),
    order_date  date NOT NULL,
    ship_date   date NOT NULL,
    ship_mode   text NOT NULL,
    country     text NOT NULL,
    city        text NOT NULL,
    state       text NOT NULL,
    postal_code text,
    region      text NOT NULL
);

-- One row per product within an order (the grain of the source file).
CREATE TABLE order_lines (
    row_id      integer PRIMARY KEY,
    order_id    text    NOT NULL REFERENCES orders (order_id),
    product_key integer NOT NULL REFERENCES products (product_key),
    sales       numeric NOT NULL,
    quantity    integer NOT NULL,
    discount    numeric NOT NULL,
    profit      numeric NOT NULL
);

INSERT INTO customers (customer_id, customer_name, segment)
SELECT DISTINCT customer_id, customer_name, segment
FROM stg_superstore;

-- chr(160) is the non-breaking space; replace it with a normal space.
INSERT INTO products (product_id, product_name, category, sub_category)
SELECT DISTINCT product_id, replace(product_name, chr(160), ' '), category, sub_category
FROM stg_superstore;

-- Dates are US month/day/year. lpad restores leading zeros on postal codes
-- in case Excel stripped them (5-digit codes are unchanged).
INSERT INTO orders (order_id, customer_id, order_date, ship_date, ship_mode,
                    country, city, state, postal_code, region)
SELECT DISTINCT order_id, customer_id,
       to_date(order_date, 'MM/DD/YYYY'),
       to_date(ship_date, 'MM/DD/YYYY'),
       ship_mode, country, city, state,
       lpad(postal_code, 5, '0'),
       region
FROM stg_superstore;

-- Each line finds its product by ID + cleaned name, and gets the surrogate key.
INSERT INTO order_lines (row_id, order_id, product_key, sales, quantity, discount, profit)
SELECT s.row_id::integer, s.order_id, p.product_key,
       s.sales::numeric, s.quantity::integer, s.discount::numeric, s.profit::numeric
FROM stg_superstore s
JOIN products p
  ON p.product_id = s.product_id
 AND p.product_name = replace(s.product_name, chr(160), ' ');

COMMIT;