# Light Take Home

This repository contains a small FastAPI application that recommends the best energy tariff based on uploaded usage data.

## Running

Setup your secrets by pasting your `OPENAI_API_KEY` into a `.env` file.

Install dependencies and start the server with uvicorn:

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API exposes two endpoints:

- `POST /recommend` – upload a CSV file with usage data and get tariff recommendations.
- `POST /explain` – upload the same usage CSV and receive an AI generated email summarising which tariff is best and why.

The `/recommend` endpoint processes the CSV stream month by month so even large
files can be handled without loading everything into memory.

### `/recommend` 
#### Input
The endpoint expects the following inputs:
- `usageData`: csv file
- `considerGeneration`: optional, boolean, default `True`
  - Determines whether the user's generated electricity is subtracted from their usage billing
- `allowPlanSwitching`: optional, boolean, default `True`
  - Whether the user is allowed to switch tariff plans each month to optimize cost

#### Output Format
The endpoint returns JSON with the cheapest plan.
If `allowPlanSwitching` is false the result looks like:

```json
{"plan": "<PLAN>", "cost": <TOTAL>}
```

With switching allowed the output contains per-month information:

```json
{"months": {"YYYY-MM": {"plan": "<PLAN>", "cost": <MONTH_COST>}, ...}}
```

The response also includes a `metrics` object detailing the cost and usage
breakdown for every plan and month. The `/explain` endpoint relies on these
values to generate its summary.


### `/explain`
#### Input
The endpoint expects the following inputs:
- `usageData`: csv file
- `userId`: user id that we would use when integrating with email-sending

#### Output Format
The endpoint returns the email that was sent to the user, in plain text.
