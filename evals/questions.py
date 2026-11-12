"""Phase 6: the evaluation set. 30 business questions, each with a hand-written SQL answer key.

The expected answer is whatever the key SQL returns, so the numbers are never typed by hand.
A question passes when every value in the key result appears in the agent's result table.

kind:
  basic  - plain aggregation, no company rule needed
  rule   - needs a definition from docs/business_notes.md (VIP, late, heavy discount, ...)
  chart  - the user asks for a chart; the agent should also draw one
"""

QUESTIONS = [
    # ---------- basic ----------
    {"id": "q01", "kind": "basic",
     "question": "What are our total sales, total profit and profit margin?",
     "sql": """SELECT ROUND(SUM(sales), 2), ROUND(SUM(profit), 2), ROUND(100 * SUM(profit) / SUM(sales), 2)
               FROM order_lines"""},
    {"id": "q02", "kind": "basic",
     "question": "How many orders have we received in total?",
     "sql": "SELECT COUNT(DISTINCT order_id) FROM orders"},
    {"id": "q03", "kind": "basic",
     "question": "How many customers do we have?",
     "sql": "SELECT COUNT(*) FROM customers"},
    {"id": "q04", "kind": "rule",
     "question": "What is our average order value?",
     "sql": "SELECT ROUND(SUM(sales) / COUNT(DISTINCT order_id), 2) FROM order_lines"},
    {"id": "q05", "kind": "basic",
     "question": "What are total sales and profit for each category?",
     "sql": """SELECT p.category, ROUND(SUM(l.sales), 2), ROUND(SUM(l.profit), 2)
               FROM order_lines l JOIN products p USING (product_key) GROUP BY 1"""},
    {"id": "q06", "kind": "basic",
     "question": "Who are our top 5 customers by sales?",
     "sql": """SELECT c.customer_name FROM order_lines l JOIN orders o USING (order_id)
               JOIN customers c USING (customer_id)
               GROUP BY c.customer_id, c.customer_name ORDER BY SUM(l.sales) DESC LIMIT 5"""},
    {"id": "q07", "kind": "basic",
     "question": "Which 3 sub-categories have the lowest total profit?",
     "sql": """SELECT p.sub_category, ROUND(SUM(l.profit), 2) FROM order_lines l JOIN products p USING (product_key)
               GROUP BY 1 ORDER BY 2 LIMIT 3"""},
    {"id": "q08", "kind": "basic",
     "question": "What is the profit margin for each region?",
     "sql": """SELECT o.region, ROUND(100 * SUM(l.profit) / SUM(l.sales), 2)
               FROM order_lines l JOIN orders o USING (order_id) GROUP BY 1"""},
    {"id": "q09", "kind": "basic",
     "question": "Which region has the lowest profit margin?",
     "sql": """SELECT o.region FROM order_lines l JOIN orders o USING (order_id)
               GROUP BY 1 ORDER BY SUM(l.profit) / SUM(l.sales) LIMIT 1"""},
    {"id": "q10", "kind": "basic",
     "question": "What is the average number of days to ship for each ship mode?",
     "sql": "SELECT ship_mode, ROUND(AVG(ship_date - order_date), 1) FROM orders GROUP BY 1"},
    {"id": "q11", "kind": "basic",
     "question": "What are total sales by customer segment?",
     "sql": """SELECT c.segment, ROUND(SUM(l.sales), 2) FROM order_lines l JOIN orders o USING (order_id)
               JOIN customers c USING (customer_id) GROUP BY 1"""},
    {"id": "q12", "kind": "basic",
     "question": "Which 5 states have the highest sales?",
     "sql": """SELECT o.state FROM order_lines l JOIN orders o USING (order_id)
               GROUP BY 1 ORDER BY SUM(l.sales) DESC LIMIT 5"""},
    {"id": "q13", "kind": "basic",
     "question": "Which city has the highest total sales?",
     "sql": """SELECT o.city FROM order_lines l JOIN orders o USING (order_id)
               GROUP BY 1 ORDER BY SUM(l.sales) DESC LIMIT 1"""},
    {"id": "q14", "kind": "basic",
     "question": "How many units did we sell in 2017?",
     "sql": """SELECT SUM(l.quantity) FROM order_lines l JOIN orders o USING (order_id)
               WHERE o.order_date >= '2017-01-01' AND o.order_date < '2018-01-01'"""},
    {"id": "q15", "kind": "basic",
     "question": "What are total sales for each ship mode?",
     "sql": """SELECT o.ship_mode, ROUND(SUM(l.sales), 2) FROM order_lines l JOIN orders o USING (order_id)
               GROUP BY 1"""},
    {"id": "q16", "kind": "basic",
     "question": "Which sub-categories lose money?",
     "sql": """SELECT p.sub_category FROM order_lines l JOIN products p USING (product_key)
               GROUP BY 1 HAVING SUM(l.profit) < 0"""},

    # ---------- needs a business rule ----------
    {"id": "q17", "kind": "rule",
     "question": "How many VIP customers do we have?",
     "sql": """SELECT COUNT(*) FROM (SELECT o.customer_id FROM orders o JOIN order_lines l USING (order_id)
               GROUP BY 1 HAVING SUM(l.sales) >= 10000) v"""},
    {"id": "q18", "kind": "rule",
     "question": "How much did our VIP customers spend in total?",
     "sql": """SELECT ROUND(SUM(s), 2) FROM (SELECT SUM(l.sales) s FROM orders o JOIN order_lines l USING (order_id)
               GROUP BY o.customer_id HAVING SUM(l.sales) >= 10000) v"""},
    {"id": "q19", "kind": "rule",
     "question": "How many orders were late, and what percentage of all orders is that?",
     "sql": """SELECT COUNT(*) FILTER (WHERE ship_date - order_date > 5),
               ROUND(100.0 * COUNT(*) FILTER (WHERE ship_date - order_date > 5) / COUNT(*), 1) FROM orders"""},
    {"id": "q20", "kind": "rule",
     "question": "How many late orders were there for each ship mode?",
     "sql": "SELECT ship_mode, COUNT(*) FILTER (WHERE ship_date - order_date > 5) FROM orders GROUP BY 1"},
    {"id": "q21", "kind": "rule",
     "question": "What was the total profit on heavily discounted order lines?",
     "sql": "SELECT ROUND(SUM(profit), 2) FROM order_lines WHERE discount >= 0.4"},
    {"id": "q22", "kind": "rule",
     "question": "How many order lines had a heavy discount?",
     "sql": "SELECT COUNT(*) FROM order_lines WHERE discount >= 0.4"},
    {"id": "q23", "kind": "rule",
     "question": "What percentage of order lines were discounted?",
     "sql": "SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE discount > 0) / COUNT(*), 1) FROM order_lines"},
    {"id": "q24", "kind": "rule",
     "question": "How many active customers did we have in 2017?",
     "sql": """SELECT COUNT(DISTINCT customer_id) FROM orders
               WHERE order_date >= '2017-01-01' AND order_date < '2018-01-01'"""},
    {"id": "q25", "kind": "rule",
     "question": "What were our total sales last year?",
     "sql": """SELECT ROUND(SUM(l.sales), 2) FROM order_lines l JOIN orders o USING (order_id)
               WHERE o.order_date >= '2017-01-01' AND o.order_date < '2018-01-01'"""},
    {"id": "q26", "kind": "rule",
     "question": "What was our year-over-year sales growth in 2017?",
     "sql": """WITH y AS (SELECT EXTRACT(YEAR FROM o.order_date) yr, SUM(l.sales) s
               FROM order_lines l JOIN orders o USING (order_id) GROUP BY 1)
               SELECT ROUND(100 * (a.s - b.s) / b.s, 1) FROM y a JOIN y b ON b.yr = a.yr - 1 WHERE a.yr = 2017"""},
    {"id": "q27", "kind": "rule",
     "question": "What is the average order value for each customer segment?",
     "sql": """SELECT c.segment, ROUND(SUM(l.sales) / COUNT(DISTINCT o.order_id), 2)
               FROM order_lines l JOIN orders o USING (order_id) JOIN customers c USING (customer_id) GROUP BY 1"""},

    # ---------- charts ----------
    {"id": "q28", "kind": "chart",
     "question": "Show total sales by category as a bar chart",
     "sql": """SELECT p.category, ROUND(SUM(l.sales), 2) FROM order_lines l JOIN products p USING (product_key)
               GROUP BY 1"""},
    {"id": "q29", "kind": "chart",
     "question": "Show total sales by year as a line chart",
     "sql": """SELECT EXTRACT(YEAR FROM o.order_date)::int, ROUND(SUM(l.sales), 2)
               FROM order_lines l JOIN orders o USING (order_id) GROUP BY 1"""},
    {"id": "q30", "kind": "chart",
     "question": "Plot monthly sales in 2017 as a line chart",
     "sql": """SELECT ROUND(SUM(l.sales), 2) FROM order_lines l JOIN orders o USING (order_id)
               WHERE o.order_date >= '2017-01-01' AND o.order_date < '2018-01-01'
               GROUP BY DATE_TRUNC('month', o.order_date)"""},
]
