# Demo script

## Before the meeting (10 minutes early)

1. Run `./start_demo.sh` from the project folder. It starts Docker Desktop, the `sales-db` database, the API and the UI.
2. Open http://localhost:8501. The sidebar badge should say **API and database online**, and the KPI cards should show $2.30M sales.
3. Leave **Reuse saved answers** on. The six sidebar questions are saved, so they answer instantly and cost 0 Gemini requests.
4. Close other tabs and zoom the browser to about 110% so the client can read it.

If the script fails, start the parts by hand:

```bash
open -a Docker
docker start sales-db
source .venv/bin/activate
HF_HUB_OFFLINE=1 uvicorn api:app --port 8000     # terminal 1
streamlit run app.py                             # terminal 2
```

## The five questions (about 10 minutes)

| # | Question (sidebar button) | What to point out |
|---|---|---|
| 1 | What are our total sales, total profit and profit margin? | Plain-English answer. Open the **SQL** tab: every number comes from a real query, and the margin follows the company's rule (sum first, then divide). |
| 2 | Show total sales by category as a bar chart | Interactive chart: hover over a bar for exact values. Technology leads with $836K. |
| 3 | How many VIP customers do we have, and how much did they spend in total? | The **Business rule** tab: the assistant looked up *your* definition of VIP (lifetime sales of $10,000 or more) before writing SQL. Answer: 20 VIPs, $264,909.67. |
| 4 | How many orders were late, and what percentage of all orders is that? | Another company rule (late = more than 5 days to ship). Answer: 904 orders, 18%. Open **Agent steps** to show the reasoning: search the notes, then run SQL. |
| 5 | Which sub-categories lose money? | A real insight: Tables, Bookcases and Supplies lose money. Good lead-in to "what would you ask about your own data?" |

Backup question: **Show total sales by year as a line chart** (sales grew from $484K in 2014 to $733K in 2017).

## Asking a new question live

- Type it in the box at the bottom. A new question takes 25 to 45 seconds and uses about 3 of the 20 free Gemini requests per day, so plan on 4 or 5 live questions at most.
- If the first model's daily quota runs out, the API switches to a second free model automatically.
- Good live questions: "Which region has the lowest profit margin?", "Who are our top 5 customers by sales?", "How much profit did heavily discounted order lines make?"

## Talking points

- **Trust:** every answer shows the SQL, the raw rows and the business rule used. Nothing is a black box.
- **Safety:** the AI uses a read-only database user with a 5-second timeout, plus a check that blocks anything other than a SELECT. It cannot change or delete data.
- **Your definitions:** company terms live in a plain business-notes document. Change the notes and the assistant follows the new rule, with no code changes.
- **Cost:** runs on the Gemini free tier. Repeated questions are answered from saved results at no cost.
