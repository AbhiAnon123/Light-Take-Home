from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import json
import os
import openai

from app.managers.tariff_manager import calculate_from_csv
from app.configs.tariffs import load_tariffs

router = APIRouter()

load_dotenv()

EXPLAIN_SYSTEM_PROMPT = f"""
You are a helpful expert energy consultant.
Given a customer's energy usage data, we have generated an analysis of which tariff plan will be cheapest to them out of a given set of options.
Using the analysis provided as input, write a concise email explaining which tariff plan is cheapest, how it compares to the alternatives and what factors most affect the cost.

<tariff-plan-options>
## Tariff Plan Options:
{json.dumps(load_tariffs(), indent=2)}
</tariff-plan-options>

## Description of the Input Data
The input will include the most cost-efficient plan option, the cost and usage metrics of each, as well 
as a detailed breakdown of the cost + usage based on the different components of each given plan.\n
A single tariff plan consists of several elements:
1. A base fee, monthly
2. A list of configs that apply by hour of the day
    - Each of these configs has a start hour and end hour, or by default applies to all hours of the day
    - Each of the configs also optionally has a billedAfterUsage field, which means that the rate of that config applies after the monthly usage has hit a certain limit
    - The billedAfterUsage value is in kWh
    - The cost of each config is in cents per kWh


## Response
Your response should be a respectful, professional, and friendly email to the customer.
It should be formatted as such:

Dear Customer,

Thank you for being a valued customer at Light. We are reaching out today to offer some recommendations on your energy usage.
There are a few different options on tariff plans, and we'd love to give you some recommendations on which to choose.

According to our analysis, the cheapest plan for you would be:
**Plan Name**

Here are the details of that plan:
**Details of the configs (cheaper billing at night, x cents until 500kWh, then x cents, or maybe it's just a flat rate, etc.)**

Here's why it's your best option:
**Describe where the plan wins out against the other plans based on the breakdown. E.g. you are using around this much electricity during the night hours of 6-12 falling under the reduced rate of this tariff plan.**
"""


@router.post("/recommend")
async def recommend(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    result = calculate_from_csv(usageData.file, considerGeneration, allowPlanSwitching)
    return JSONResponse(result)


@router.post("/explain")
async def explain(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    """Return an LLM generated explanation of the best tariff option."""
    result = calculate_from_csv(usageData.file, considerGeneration, allowPlanSwitching)

    openai.api_key = os.getenv("OPENAI_API_KEY")
    system_prompt = EXPLAIN_SYSTEM_PROMPT
    user_message = json.dumps(result, indent=2)
    completion = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
    )
    explanation = completion.choices[0].message.content
    return JSONResponse({"explanation": explanation, "analysis": result})
    # We simple return response but this could trigger the email by publishing message or api call to our email provider service
