# Light Take Home

This repository contains a small FastAPI application that recommends the best energy tariff based on uploaded usage data.

## Running

Setup your secrets by pasting your `OPENAI_API_KEY` into a `.env` file.

Install dependencies and start the server with uvicorn:

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API exposes the following endpoints:

- `POST /v1/recommend` – upload a CSV file and receive the cheapest plan with a brief analysis based on the actual usage data. Detailed metrics are omitted from the response.
- `POST /v2/recommend` – returns the cheapest plan(s) along with full per‑month metrics and an annual analysis calculated from averaged data.
- `POST /explain` – upload the same usage CSV and get an email style explanation based on the `/v2/recommend` output.

The recommendation endpoints process the CSV stream month by month so even large
files can be handled without loading everything into memory.

### `/v1/recommend`
#### Input
The endpoint expects the following inputs:
- `usageData`: csv file
- `considerGeneration`: optional, boolean, default `True`
  - Determines whether the user's generated electricity is subtracted from their usage billing
- `allowPlanSwitching`: optional, boolean, default `True`
  - Whether the user is allowed to switch tariff plans each month to optimize cost

#### Output Format
The endpoint returns JSON with the cheapest plan plus an `analysis` section summarising the recommendation.
If `allowPlanSwitching` is false the result looks like:

```json
{"plan": "<PLAN>", "cost": <TOTAL>}
```

With switching allowed the output contains per-month information:

```json
{"months": {"YYYY-MM": {"plan": "<PLAN>", "cost": <MONTH_COST>}, ...}}
```
In both cases the `analysis` field repeats these recommendations based solely on the uploaded data without averaging.

### `/v2/recommend`
This endpoint returns the same fields as v1 but also includes:
* `metrics` – cost and usage breakdown for every plan and month
* `averageMetrics` – the monthly averages of those metrics used for annual comparisons
* `analysis` – summary of the best plan for the upcoming year based on those averages
The `/explain` endpoint relies on these values to generate its summary.

### `/explain`
Accepts the same parameters as the recommendation endpoints. It generates a friendly email that includes a GPT-4o explanation of the results from `/v2/recommend`.
