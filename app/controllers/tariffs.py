from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import json
import os
import openai

from app.managers.tariff_manager import calculate_from_csv

router = APIRouter()

load_dotenv()


@router.post("/v1/recommend")
async def recommend_v1(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    result = calculate_from_csv(
        usageData.file,
        considerGeneration,
        allowPlanSwitching,
        use_averages_analysis=False,
    )
    # v1 omits heavy metric details
    result.pop("metrics", None)
    result.pop("averageMetrics", None)
    return JSONResponse(result)


@router.post("/v2/recommend")
@router.post("/recommend")
async def recommend_v2(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    result = calculate_from_csv(
        usageData.file,
        considerGeneration,
        allowPlanSwitching,
        use_averages_analysis=True,
    )
    return JSONResponse(result)


@router.post("/explain")
async def explain(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    """Return an LLM generated explanation of the best tariff option."""
    result = calculate_from_csv(
        usageData.file,
        considerGeneration,
        allowPlanSwitching,
        use_averages_analysis=True,
    )

    openai.api_key = os.getenv("OPENAI_API_KEY")
    system_prompt = (
        "You are a helpful energy consultant. Using the provided tariff analysis, "
        "explain why the recommended plan or plans are best. If multiple months are present, "
        "give a brief reason for each month without mentioning the year."
    )
    user_message = json.dumps(result, indent=2)
    completion = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
    )
    text = completion.choices[0].message.content
    prefix = (
        "Dear Customer,\n\n"
        "Thank you for being a valued customer with us! Here is your tariff plan recommendations for the next year"
    )
    if allowPlanSwitching:
        prefix += ", split by month:\n\n"
    else:
        prefix += ":\n\n"
    email = prefix + text + "\n\nThank you again!\nSincerely, Light"
    return JSONResponse({"email": email, "analysis": result})
