-- Answer key for questions that need the business notes (Phase 3 RAG).
-- Each query applies one rule from docs/business_notes.md exactly.

-- A1: How many VIP customers? (VIP = lifetime sales >= 10,000)
SELECT COUNT(*) AS vip_customers
FROM (
    SELECT o.customer_id
    FROM orders o
    JOIN order_lines ol ON ol.order_id = o.order_id
    GROUP BY o.customer_id
    HAVING SUM(ol.sales) >= 10000
) AS vips;

-- A2: How many orders were late? (late = more than 5 days from order to ship)
SELECT
    COUNT(*) FILTER (WHERE ship_date - order_date > 5) AS late_orders,
    COUNT(*) AS all_orders,
    ROUND(100.0 * COUNT(*) FILTER (WHERE ship_date - order_date > 5) / COUNT(*), 1) AS late_pct
FROM orders;

-- A3: How did heavily discounted lines do? (heavy = discount >= 0.4)
SELECT
    COUNT(*) AS heavy_lines,
    ROUND(SUM(sales)::numeric, 2) AS sales,
    ROUND(SUM(profit)::numeric, 2) AS profit
FROM order_lines
WHERE discount >= 0.4;