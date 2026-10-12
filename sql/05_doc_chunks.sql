-- Step 3.3: a table for the business notes and their embeddings.
-- Run as analyst (the owner). Safe to re-run: it rebuilds the empty table.
BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS doc_chunks;

CREATE TABLE doc_chunks (
    chunk_id   serial PRIMARY KEY,
    source     text NOT NULL,         -- file the chunk came from
    heading    text NOT NULL,         -- the "## " section title
    content    text NOT NULL,         -- section text that will be sent to Gemini
    embedding  vector(384) NOT NULL   -- all-MiniLM-L6-v2 output
);

-- The AI user may read the notes, never change them.
GRANT SELECT ON doc_chunks TO ai_reader;

COMMIT;
