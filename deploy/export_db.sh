#!/usr/bin/env bash
# Phase 9: copy the local database to a hosted Postgres (Neon, Supabase, ...).
#
# Usage:
#   ./deploy/export_db.sh                         # writes deploy/sales_dump.sql
#   ./deploy/export_db.sh "postgresql://..."      # also loads it into that database
#
# The dump holds the 4 clean tables and the business-note embeddings, not the staging table.
# It is git-ignored: the raw data is not ours to publish.
set -euo pipefail
cd "$(dirname "$0")/.."

docker exec sales-db pg_dump -U analyst -d sales --no-owner --no-privileges \
  -t customers -t products -t orders -t order_lines -t doc_chunks > deploy/sales_dump.sql
echo "Wrote deploy/sales_dump.sql ($(wc -c < deploy/sales_dump.sql) bytes)"

if [ $# -ge 1 ]; then
  psql "$1" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector;"
  psql "$1" -v ON_ERROR_STOP=1 -f deploy/sales_dump.sql
  echo "Loaded. Now create the read-only role (see docs/DEPLOYMENT.md, step 2)."
fi
