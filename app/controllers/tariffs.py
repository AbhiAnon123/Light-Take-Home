from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse

from app.managers.tariff_manager import calculate_from_csv

router = APIRouter()


@router.post("/recommend")
async def recommend(
    usageData: UploadFile = File(...),
    considerGeneration: bool = Query(True),
    allowPlanSwitching: bool = Query(True),
):
    result = calculate_from_csv(usageData.file, considerGeneration, allowPlanSwitching)
    return JSONResponse(result)


@router.get("/explain")
async def explain():
    """TODO: implement explanation of latest recommendation"""
    return JSONResponse({"detail": "TODO"})
