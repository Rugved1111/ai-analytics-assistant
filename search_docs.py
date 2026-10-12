"""Step 3.4: find the business-note chunks most relevant to a question."""
import os

import psycopg
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

# Must be the SAME model ingest_docs.py used, or the numbers aren't comparable.
MODEL_NAME = "all-MiniLM-L6-v2"
model = SentenceTransformer(MODEL_NAME)


def to_pgvector(vector):
    """Turn a list of numbers into pgvector's text format: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


def search_docs(question, k=3):
    """Return the k chunks closest in meaning to the question.

    Each result is a dict with heading, content and distance
    (0 = same meaning, bigger = less related).
    """
    question_vector = to_pgvector(model.encode(question))
    sql = """
        SELECT heading, content, embedding <=> %s::vector AS distance
        FROM doc_chunks
        ORDER BY distance
        LIMIT %s
    """
    # Read-only user: the app only ever reads the notes.
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["AI_DB_USER"],
        password=os.environ["AI_DB_PASSWORD"],
    ) as conn:
        rows = conn.execute(sql, (question_vector, k)).fetchall()
    return [
        {"heading": h, "content": c, "distance": round(float(d), 3)}
        for h, c, d in rows
    ]


if __name__ == "__main__":
    questions = [
        "Who are our VIP customers?",
        "Which orders were late?",
        "How much did heavily discounted items lose us?",
        "What was the average order value?",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        for r in search_docs(q, k=3):
            print(f"  {r['distance']:.3f}  {r['heading']}")