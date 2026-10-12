"""Step 3.3b: split business_notes.md into chunks, embed them, store them in doc_chunks.

Runs as analyst (the owner), because ai_reader is read-only. Safe to re-run:
it empties the table first, so after editing the notes just run it again.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

NOTES_FILE = Path("docs/business_notes.md")
MODEL_NAME = "all-MiniLM-L6-v2"


def split_into_chunks(text):
    """Return a list of (heading, content) pairs, one per '## ' section."""
    chunks = []
    heading = None
    lines = []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading is not None:
                chunks.append((heading, "\n".join(lines).strip()))
            heading = line[3:].strip()
            lines = []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        chunks.append((heading, "\n".join(lines).strip()))
    return chunks


def to_pgvector(vector):
    """pgvector accepts a vector written as text: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


def main():
    load_dotenv()
    chunks = split_into_chunks(NOTES_FILE.read_text(encoding="utf-8"))
    print(f"Found {len(chunks)} chunks in {NOTES_FILE}")

    model = SentenceTransformer(MODEL_NAME)
    # Embed heading + content together so the heading's words count too.
    texts = [f"{heading}\n{content}" for heading, content in chunks]
    vectors = model.encode(texts)
    print(f"Each chunk became {len(vectors[0])} numbers")

    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE doc_chunks RESTART IDENTITY")
            for (heading, content), vector in zip(chunks, vectors):
                cur.execute(
                    "INSERT INTO doc_chunks (source, heading, content, embedding) "
                    "VALUES (%s, %s, %s, %s::vector)",
                    (str(NOTES_FILE), heading, content, to_pgvector(vector)),
                )
    # Leaving the 'with' block commits; any error rolls everything back.
    print(f"Stored {len(chunks)} chunks in doc_chunks")


if __name__ == "__main__":
    main()