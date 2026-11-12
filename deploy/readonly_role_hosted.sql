-- Phase 9: the read-only ai_reader role on a hosted Postgres (Neon, Supabase).
-- Same rules as sql/04_readonly_role.sql, but works whatever the database is called.
-- Usage: psql "$OWNER_DATABASE_URL" -v ai_password="a-long-random-password" -f deploy/readonly_role_hosted.sql
\set ON_ERROR_STOP on

SELECT 'CREATE ROLE ai_reader LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_reader')
\gexec

ALTER ROLE ai_reader WITH LOGIN PASSWORD :'ai_password';
ALTER ROLE ai_reader SET default_transaction_read_only = on;
ALTER ROLE ai_reader SET statement_timeout = '5s';

SELECT format('GRANT CONNECT ON DATABASE %I TO ai_reader', current_database())
\gexec

GRANT USAGE ON SCHEMA public TO ai_reader;
GRANT SELECT ON customers, products, orders, order_lines, doc_chunks TO ai_reader;
