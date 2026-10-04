-- Q1: total sales, total profit, profit margin %
SELECT round(sum(sales), 2)                    AS total_sales,
       round(sum(profit), 2)                   AS total_profit,
       round(100 * sum(profit) / sum(sales), 2) AS margin_pct
FROM order_lines;


-- Q2: sales and profit by category
SELECT p.category,
       round(sum(l.sales), 2)  AS sales,
       round(sum(l.profit), 2) AS profit
FROM order_lines l
JOIN products p ON p.product_key = l.product_key
GROUP BY p.category
ORDER BY sales DESC;

-- Q3: top 5 customers by total sales
SELECT c.customer_name,
       round(sum(l.sales), 2) AS total_sales
FROM order_lines l
JOIN orders o    ON o.order_id = l.order_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name
ORDER BY total_sales DESC
LIMIT 5;
-- Q4: number of orders per year
SELECT extract(year FROM order_date)::int AS year,
       count(*)                           AS orders
FROM orders
GROUP BY year
ORDER BY year;



-- Q5: average order value (per order, not per line)
SELECT round(sum(sales) / count(DISTINCT order_id), 2) AS avg_order_value
FROM order_lines;

-- Q6: monthly sales in 2017
SELECT date_trunc('month', o.order_date)::date AS month,
       round(sum(l.sales), 2)                  AS sales
FROM order_lines l
JOIN orders o ON o.order_id = l.order_id
WHERE o.order_date >= '2017-01-01' AND o.order_date < '2018-01-01'
GROUP BY month
ORDER BY month;

-- Q7: 3 sub-categories with the lowest total profit
SELECT p.sub_category,
       round(sum(l.profit), 2) AS profit
FROM order_lines l
JOIN products p ON p.product_key = l.product_key
GROUP BY p.sub_category
ORDER BY profit ASC
LIMIT 3;


-- Q8: profit margin % by region
SELECT o.region,
       round(sum(l.sales), 2)                      AS sales,
       round(sum(l.profit), 2)                     AS profit,
       round(100 * sum(l.profit) / sum(l.sales), 2) AS margin_pct
FROM order_lines l
JOIN orders o ON o.order_id = l.order_id
GROUP BY o.region
ORDER BY margin_pct DESC;


-- Q9: average days between order and shipping, by ship mode
SELECT ship_mode,
       round(avg(ship_date - order_date), 1) AS avg_days_to_ship,
       count(*)                              AS orders
FROM orders
GROUP BY ship_mode
ORDER BY avg_days_to_ship;


-- Q10: year-over-year sales growth % by category
WITH yearly AS (
    SELECT p.category,
           extract(year FROM o.order_date)::int AS year,
           sum(l.sales)                         AS sales
    FROM order_lines l
    JOIN orders o   ON o.order_id = l.order_id
    JOIN products p ON p.product_key = l.product_key
    GROUP BY p.category, year
)
SELECT category,
       year,
       round(sales, 2) AS sales,
       round(100 * (sales - LAG(sales) OVER w) / LAG(sales) OVER w, 1) AS yoy_growth_pct
FROM yearly
WINDOW w AS (PARTITION BY category ORDER BY year)
ORDER BY category, year;




