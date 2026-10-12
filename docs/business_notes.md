# Business notes: Superstore sales

## About the data
Retail sales of furniture, office supplies and technology to customers across the United States, from January 2014 to December 2017. All amounts are in US dollars. One row in order_lines is one product on one order.

## Sales and revenue
Sales means revenue after discount, taken from order_lines.sales. When someone says revenue, turnover or income, they mean sales.

## Profit and profit margin
Profit comes from order_lines.profit and can be negative. Profit margin = total profit / total sales * 100, shown as a percentage rounded to 2 decimals. Always sum first and then divide. Never average the margins of individual lines.

## Orders and average order value
An order is one order_id, and one order can have several order lines. Count orders with COUNT(DISTINCT order_id). Average order value (AOV) = total sales / number of distinct orders.

## Discounts
Discount is stored as a fraction: 0.2 means 20% off. A discounted line is one with discount greater than 0. A heavy discount is a discount of 0.4 or more.

## Shipping
Ship days = ship_date - order_date. Ship modes are Same Day, First Class, Second Class and Standard Class. An order is late if it took more than 5 days to ship, whatever the ship mode.

## Customers and segments
Segments are Consumer, Corporate and Home Office. Rank top customers by total sales unless profit is asked for. A VIP customer has lifetime sales of 10,000 or more. A customer is active in a year if they placed at least one order in that year.

## Regions
There are four regions: Central, East, South and West. The address is stored on the order, not the customer, so one customer can appear in several regions.

## Products
There are three categories (Furniture, Office Supplies, Technology) and 17 sub-categories. product_id is not unique: 32 IDs each cover two different products. Always join order_lines to products on product_key.

## Time periods
Years are calendar years. Last year means 2017, the latest full year in the data. Year-over-year growth = (this year - previous year) / previous year * 100.

## Known business facts
Peak season is September to December. Furniture has the thinnest margin, and Tables and Bookcases lose money. Central is the weakest region by margin.