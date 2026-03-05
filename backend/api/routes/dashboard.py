"""
Dashboard Analytics Routes
"""
from fastapi import APIRouter
from pathlib import Path
import json, pickle

router = APIRouter()

MODEL_DIR = Path(__file__).parent.parent.parent / "models"

# Real statistics computed from datasets (hardcoded from analysis)
STATS = {
    "total_policies": 33493,
    "avg_premium": 272603,
    "claim_approval_rate": 73.85,
    "avg_claim_amount": 725796,
    "ncb_rate": 75.96,
    "accident_rate": 32.99,
    "model_auc": 0.7200,
    "model_r2": 0.9990,
    "age_risk": [
        {"age_group": "16-25", "avg_risk": 82.06},
        {"age_group": "26-35", "avg_risk": 41.88},
        {"age_group": "36-45", "avg_risk": 43.62},
        {"age_group": "46-55", "avg_risk": 49.12},
        {"age_group": "56-65", "avg_risk": 48.56},
        {"age_group": "65+",   "avg_risk": 63.41},
    ],
    "province_risk": [
        {"province": "Western", "avg_risk": 55.2, "claim_count": 13390},
        {"province": "Central", "avg_risk": 55.1, "claim_count": 4020},
        {"province": "Eastern", "avg_risk": 50.3, "claim_count": 2560},
        {"province": "Northern", "avg_risk": 50.7, "claim_count": 2100},
        {"province": "North Western", "avg_risk": 50.6, "claim_count": 2800},
        {"province": "North Central", "avg_risk": 50.6, "claim_count": 1900},
        {"province": "Uva", "avg_risk": 50.2, "claim_count": 1750},
        {"province": "Southern", "avg_risk": 50.1, "claim_count": 3200},
        {"province": "Sabaragamuwa", "avg_risk": 49.7, "claim_count": 1495},
    ],
    "claim_types": [
        {"type": "Accidental Damage", "count": 18136, "avg_amount": 635000},
        {"type": "Third Party Property", "count": 3220, "avg_amount": 485000},
        {"type": "Windscreen", "count": 2990, "avg_amount": 125000},
        {"type": "Theft - Parts", "count": 2590, "avg_amount": 380000},
        {"type": "Theft - Vehicle", "count": 1820, "avg_amount": 5170000},
        {"type": "Fire", "count": 1240, "avg_amount": 4220000},
        {"type": "Flood", "count": 1010, "avg_amount": 2260000},
        {"type": "Riot", "count": 820, "avg_amount": 1620000},
        {"type": "Medical", "count": 760, "avg_amount": 195000},
        {"type": "Other", "count": 629, "avg_amount": 280000},
    ],
    "risk_distribution": [
        {"category": "Low (0-39)", "count": 9329},
        {"category": "Medium (40-69)", "count": 16589},
        {"category": "High (70+)", "count": 7575},
    ],
    "feature_importance": [
        {"feature": "Sum_Insured_LKR", "importance": 0.2468},
        {"feature": "Driver_Age", "importance": 0.2466},
        {"feature": "Years_Driving_Experience", "importance": 0.2366},
        {"feature": "Province", "importance": 0.0623},
        {"feature": "Engine_CC", "importance": 0.0588},
        {"feature": "Vehicle_Age_Years", "importance": 0.0523},
        {"feature": "Occupation", "importance": 0.0406},
        {"feature": "Previous_NCB_Percentage", "importance": 0.0279},
        {"feature": "Vehicle_Type", "importance": 0.0190},
        {"feature": "Gender", "importance": 0.0091},
    ]
}


@router.get("/dashboard/stats")
async def get_dashboard_stats():
    """Main KPIs and statistics for dashboard."""
    meta_path = MODEL_DIR / "model_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        STATS["model_auc"] = meta.get("risk_auc", STATS["model_auc"])
        STATS["model_r2"]  = meta.get("prem_r2", STATS["model_r2"])
    return STATS


@router.get("/dashboard/age-risk")
async def get_age_risk():
    return STATS["age_risk"]


@router.get("/dashboard/province-risk")
async def get_province_risk():
    return STATS["province_risk"]


@router.get("/dashboard/claim-types")
async def get_claim_types():
    return STATS["claim_types"]


@router.get("/dashboard/feature-importance")
async def get_feature_importance():
    return STATS["feature_importance"]


@router.get("/dashboard/model-metrics")
async def get_model_metrics():
    meta_path = MODEL_DIR / "model_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            return json.load(f)
    return {
        "risk_auc": STATS["model_auc"],
        "prem_r2": STATS["model_r2"],
        "calibrated": True,
        "note": "Run notebooks 03-06 to get exact metrics"
    }
