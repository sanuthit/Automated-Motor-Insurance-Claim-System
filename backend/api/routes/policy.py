from fastapi import APIRouter, HTTPException
from ...utils.schemas import PolicyRequest, PremiumResponse
from ...utils.engine import get_engine
import uuid
from datetime import datetime

router = APIRouter()

# In-memory store (replace with DB in production)
_policies = {}


@router.post("/policy/register")
async def register_policy(req: PolicyRequest):
    """Register new motor insurance policy with ML risk assessment."""
    engine = get_engine()
    if not engine.is_ready():
        raise HTTPException(status_code=503, detail="ML models not loaded")

    proposal = {
        "driver_age": req.driver_age, "years_exp": req.years_exp,
        "engine_cc": req.engine_cc, "vehicle_age": 2025 - req.vehicle_year,
        "sum_insured": req.sum_insured, "market_value": req.market_value,
        "prev_ncb": req.prev_ncb, "gender": req.gender.value,
        "province": req.province.value, "occupation": req.occupation,
        "vehicle_type": req.vehicle_type.value, "vehicle_condition": req.vehicle_condition.value,
        "is_blacklisted": "Yes" if req.is_blacklisted else "No",
        "rebate_approved": "Yes" if req.rebate_approved else "No",
        "images": "Yes" if req.images else "No", "inspection": "Yes" if req.inspection else "No",
        "reg_book": "Yes" if req.reg_book else "No", "fair_value": "Yes" if req.fair_value else "No",
    }

    result = engine.calculate(proposal)
    policy_id = f"POL{uuid.uuid4().hex[:8].upper()}"

    policy = {
        "policy_id": policy_id,
        "registration_date": datetime.now().isoformat(),
        "customer_name": req.customer_name,
        "nic": req.nic,
        "driver_age": req.driver_age,
        "province": req.province.value,
        "vehicle_model": req.vehicle_model,
        "vehicle_type": req.vehicle_type.value,
        "sum_insured": req.sum_insured,
        "gross_premium": result["gross_premium"],
        "risk_score": result["risk_score"],
        "risk_label": result["risk_label"],
        "status": "ISSUED" if result["is_insurable"] else "REJECTED",
        **result
    }
    _policies[policy_id] = policy
    return policy


@router.get("/policy/{policy_id}")
async def get_policy(policy_id: str):
    if policy_id not in _policies:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _policies[policy_id]


@router.get("/policies")
async def list_policies(skip: int = 0, limit: int = 20):
    items = list(_policies.values())
    return {"total": len(items), "policies": items[skip:skip+limit]}
