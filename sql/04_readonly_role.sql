-- 04_readonly_role.sql: a SELECT-only login for the AI. Re-runnable.
\set ON_ERROR_STOP on

-- Create the role only if it doesn't exist yet
SELECT 'CREATE ROLE ai_reader LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_reader')
\gexec

ALTER ROLE ai_reader WITH LOGIN PASSWORD :'ai_password';

-- Applied every time ai_reader connects
ALTER ROLE ai_reader SET default_transaction_read_only = on;
ALTER ROLE ai_reader SET statement_timeout = '5s';

-- Least privilege: connect, see the schema, read only the 4 clean tables
GRANT CONNECT ON DATABASE sales TO ai_reader;
GRANT USAGE ON SCHEMA public TO ai_reader;
GRANT SELECT ON customers, products, orders, order_lines TO ai_reader;