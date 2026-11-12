# Deployment plan (free tier)

Goal: a public link clients can open, at $0 per month, without changing the code.

## Recommended setup

```mermaid
flowchart LR
    B[Browser] --> S[Streamlit Community Cloud<br/>app.py with API_URL=inprocess]
    S --> G[Gemini API<br/>free tier]
    S -->|read-only ai_reader, SSL| N[(Neon Postgres<br/>free plan, pgvector)]
```

| Piece | Service | Why |
|---|---|---|
| Database | **Neon** free plan (Supabase free also works) | Managed Postgres with the `vector` extension. Our data is about 1.2 MB, far below the free storage limit. |
| App | **Streamlit Community Cloud** | Free hosting for Streamlit apps, deployed straight from GitHub. |
| API | Runs **inside** the Streamlit process (`API_URL=inprocess`) | One free service instead of two. The FastAPI code is unchanged: Streamlit calls it through FastAPI's in-process `TestClient`. |
| LLM | Gemini free tier | Same as local. |

Check the current free-plan limits on each provider's pricing page before relying on them. Free plans can change, and free databases may pause when idle (the first request then takes a few extra seconds).

## Steps

### 1. Database (Neon)

1. Create a free Neon project (Postgres 17). Copy the owner connection string.
2. Copy the local data across. This dumps the 4 clean tables and the note embeddings, then loads them:
   ```bash
   ./deploy/export_db.sh "postgresql://OWNER:PASSWORD@HOST/neondb?sslmode=require"
   ```
3. Create the read-only role the app uses:
   ```bash
   psql "postgresql://OWNER:PASSWORD@HOST/neondb?sslmode=require" \
        -v ai_password="a-long-random-password" -f deploy/readonly_role_hosted.sql
   ```
   This gives `ai_reader` the same rules as locally: read-only transactions, a 5 second timeout and `SELECT` on the 5 tables only.

### 2. App (Streamlit Community Cloud)

1. Push the repo to GitHub (`.env` stays out of git).
2. On share.streamlit.io choose **New app**, pick the repo, branch `main` and main file `app.py`, and Python 3.12.
3. Under **Advanced settings > Secrets**, paste:
   ```toml
   GEMINI_API_KEY = "..."
   API_URL = "inprocess"
   DB_HOST = "your-endpoint.neon.tech"
   DB_PORT = "5432"
   POSTGRES_DB = "neondb"
   AI_DB_USER = "ai_reader"
   AI_DB_PASSWORD = "the password from step 1.3"
   STREAMLIT_SERVER_FILE_WATCHER_TYPE = "none"
   ```
   Streamlit Community Cloud exposes root-level secrets as environment variables, which is how `db.py` and `agent.py` read them.
4. Deploy. The first start downloads PyTorch and the embedding model, so it takes a few minutes.

To make demo questions instant on the hosted app too, commit a copy of `cache/answers.json` (it holds only answers and SQL, no secrets) or ask each question once after deploying.

### 3. Check it

- The sidebar badge says **API and database online** and the KPI cards show $2.30M sales.
- Ask "How many VIP customers do we have?" and expect 20.
- Locally, `python -m evals.run_eval` checks saved answers against the answer key.

## Alternative: one Docker container on Hugging Face Spaces

Spaces has a free CPU tier for Docker apps. Build from the existing `Dockerfile` and change the start command to:

```bash
streamlit run app.py --server.port 7860 --server.address 0.0.0.0
```

Set `API_URL=inprocess` and the same secrets as above. The database still lives on Neon.

## Before real client data

The demo setup is fine for public sample data. For a client's own data, add these first:

- **Sign-in:** Streamlit's built-in `st.login` with the client's identity provider (Google or Microsoft), so only their staff can open the app.
- **Hosting in their account:** run the same Docker image on their cloud (for example AWS App Runner or Google Cloud Run) next to their database, so data never leaves their environment.
- **LLM terms:** the free Gemini tier may use prompts to improve Google's products. For confidential data, use a paid API plan whose terms exclude training on your data, and get the client's approval for the cost first.
- **Monitoring:** log each question, the SQL, the time taken and the token count, and rerun `evals/run_eval.py` after every prompt or model change.
