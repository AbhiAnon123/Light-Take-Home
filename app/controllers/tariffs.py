from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import json
import os
import openai

from app.managers.tariff_manager import (
    calculate_from_csv,
    get_analysis_projected,
    get_analysis_email
)
from app.configs.tariffs import load_tariffs

router = APIRouter()

load_dotenv()


@router.post("/recommend")
async def recommend(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    result = calculate_from_csv(usageData.file, considerGeneration, allowPlanSwitching)
    return JSONResponse(result)


@router.post("/v2/recommend")
async def recommend_v2(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    """Recommend tariff plans based on averaged usage patterns."""
    result = get_analysis_projected(usageData.file, considerGeneration, allowPlanSwitching)
    return JSONResponse(result)


@router.post("/explain")
async def explain(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    """Return an LLM generated explanation of the best tariff option."""
    result = await get_analysis_email(usageData.file, considerGeneration, allowPlanSwitching)
    return JSONResponse(result)
    # We simple return response but this could trigger the email by publishing message or api call to our email provider service
