
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date

from backend.utils.database import get_policy, get_policy_claims, get_latest_renewal, check_blacklist, get_config
from backend.utils.engine import get_engine

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
class RenewalCalcRequest(BaseModel):
    policy_id:            str
    proposed_sum_insured: float
    new_ncb:              float = 0.0
    # optional overrides (if fetched from DB, these are pre-filled)
    current_market_value: Optional[float] = None
    years_with_company:   Optional[int]   = None


# ── GET /renewal/policy/{policy_id} ───────────────────────────────────────
@router.get("/renewal/policy/{policy_id}")
async def fetch_renewal_details(policy_id: str):
    """
    Fetch everything needed to display the renewal form:
      - policy holder details (locked fields)
      - vehicle details
      - claim history
      - previous renewal record if any
      - blacklist status
    """
    policy = get_policy(policy_id)
    if not policy:
        raise HTTPException(404, detail=f"Policy '{policy_id}' not found in database")

    claims    = get_policy_claims(policy_id)
    last_renew = get_latest_renewal(policy_id)
    bl_status  = check_blacklist(nic=policy["nic"], policy_id=policy_id)

    # Aggregate claim stats for renewal calculation
    total_claims     = len(claims)
    total_amount     = sum(c["claim_amount"] for c in claims)
    highest_claim    = max((c["claim_amount"] for c in claims), default=0)
    last_claim_days  = 999
    if claims:
        try:
            from datetime import date as dt
            last_date = dt.fromisoformat(claims[0]["claim_date"])
            last_claim_days = (dt.today() - last_date).days
        except Exception:
            pass

    # Determine new NCB
    new_ncb = 0.0
    prev_ncb = float(policy.get("ncb_pct") or 0)
    if total_claims == 0:
        # Increment NCB: 20→25→30→40→50 (standard Sri Lanka NCB scale)
        ncb_scale = [0, 20, 25, 30, 40, 50]
        idx = ncb_scale.index(min(ncb_scale, key=lambda x: abs(x - prev_ncb)))
        new_ncb = ncb_scale[min(idx + 1, len(ncb_scale) - 1)]
    else:
        new_ncb = 0.0  # NCB forfeited on any claim

    return {
        "found": True,
        "policy": {
            "policy_id":        policy["policy_id"],
            "customer_name":    policy["customer_name"],
            "nic":              policy["nic"],
            "driver_age":       policy["driver_age"],
            "gender":           policy["gender"],
            "occupation":       policy.get("occupation", "Other"),
            "years_exp":        policy.get("years_exp", 5),
            "province":         policy["province"],
        },
        "vehicle": {
            "vehicle_model":    policy["vehicle_model"],
            "vehicle_year":     policy["vehicle_year"],
            "vehicle_age":      policy["vehicle_age"],
            "engine_cc":        policy["engine_cc"],
            "vehicle_type":     policy.get("vehicle_type", "Car"),
            "vehicle_condition": policy.get("vehicle_condition", "Good"),
            "market_value":     policy["market_value"],
        },
        "current_policy": {
            "sum_insured":      policy["sum_insured"],
            "calculated_premium": policy["calculated_premium"],
            "ncb_pct":          prev_ncb,
            "is_blacklisted":   policy.get("is_blacklisted", "No"),
            "status":           policy.get("status", "Active"),
        },
        "claim_history": {
            "total_claims":         total_claims,
            "total_amount":         total_amount,
            "highest_claim":        highest_claim,
            "days_since_last_claim": last_claim_days,
            "claims":               claims[:5],  # last 5 claims
        },
        "suggested_renewal": {
            "previous_premium":     policy["calculated_premium"],
            "previous_ncb":         prev_ncb,
            "new_ncb":              new_ncb,
            "proposed_sum_insured": policy["market_value"] * 0.95,  # 95% of current MV
            "current_market_value": policy["market_value"],
            "years_with_company":   last_renew["years_with_company"] + 1 if last_renew else 1,
        },
        "blacklist": bl_status,
    }


# ── POST /renewal/calculate ────────────────────────────────────────────────
@router.post("/renewal/calculate")
async def calculate_renewal(req: RenewalCalcRequest):
    """
    Calculate renewal premium from DB data.
    Only policy_id + proposed SI + new NCB needed from UI.
    Everything else is read from DB.
    """
    policy = get_policy(req.policy_id)
    if not policy:
        raise HTTPException(404, detail=f"Policy '{req.policy_id}' not found")

    claims     = get_policy_claims(req.policy_id)
    bl_status  = check_blacklist(nic=policy["nic"], policy_id=req.policy_id)
    last_renew = get_latest_renewal(req.policy_id)

    # Load config from DB (not hardcoded)
    prev_premium = float(policy["calculated_premium"] or 0)
    prev_ncb     = float(policy.get("ncb_pct") or 0)
    cmv          = req.current_market_value or float(policy["market_value"] or 0)
    years_co     = req.years_with_company or (
        (last_renew["years_with_company"] + 1) if last_renew else 1
    )

    number_of_claims    = len(claims)
    highest_claim       = max((c["claim_amount"] for c in claims), default=0)
    total_claim_amount  = sum(c["claim_amount"] for c in claims)

    # ── Rule-based renewal logic ─────────────────────────────────────────
    base = prev_premium
    risk_factors = []

    if number_of_claims == 0:
        ncb_diff = req.new_ncb - prev_ncb
        if ncb_diff > 0:
            base = int(base * (1 - ncb_diff / 100))
            risk_factors.append(f"NCB increased {prev_ncb:.0f}% → {req.new_ncb:.0f}% (−{ncb_diff:.0f}%)")
    elif number_of_claims == 1:
        loading = 1.35 if highest_claim > 1_000_000 else 1.15
        base = int(base * loading)
        risk_factors.append(f"1 claim loading: +{int((loading-1)*100)}%")
    elif number_of_claims == 2:
        base = int(base * 1.50)
        risk_factors.append("2 claims: +50% loading")
    else:
        base = int(base * 1.80)
        risk_factors.append(f"{number_of_claims} claims: +80% loading")

    # SI vs Market Value alignment
    si_ratio = req.proposed_sum_insured / max(1, cmv)
    if si_ratio > 1.10:
        base = int(base * 1.08)
        risk_factors.append("Over-insured (SI > MV×1.1): +8%")
    elif si_ratio < 0.80:
        base = int(base * 0.95)
        risk_factors.append("Under-insured adjustment: −5%")

    # Loyalty discount
    if years_co >= 5 and number_of_claims == 0:
        base = int(base * 0.97)
        risk_factors.append(f"Loyalty discount ({years_co} years): −3%")

    # Blacklist surcharge (from DB — not user input)
    is_blacklisted = bl_status["blacklisted"]
    if is_blacklisted:
        base = int(base * 1.50)
        risk_factors.append(f"Blacklist surcharge +50%: {bl_status.get('reason','')}")

    pct_change = (base - prev_premium) / max(1, prev_premium) * 100

    if pct_change < -20 or number_of_claims >= 3 or pct_change > 50:
        recommendation = "REVIEW"
    else:
        recommendation = "APPROVE"

    # ── Also run ML risk model for explanation ────────────────────────────
    explanation = {"available": False, "message": "ML engine not used for renewal"}
    risk_score  = None
    risk_label  = None
    acc_prob    = None
    try:
        engine = get_engine()
        if engine.is_ready():
            proposal = {
                "driver_age":       policy["driver_age"],
                "years_exp":        policy.get("years_exp", 5),
                "engine_cc":        policy["engine_cc"],
                "vehicle_age":      policy["vehicle_age"],
                "sum_insured":      req.proposed_sum_insured,
                "market_value":     cmv,
                "prev_ncb":         prev_ncb,
                "province":         policy["province"],
                "gender":           policy.get("gender", "Male"),
                "occupation":       policy.get("occupation", "Other"),
                "vehicle_type":     policy.get("vehicle_type", "Car"),
                "vehicle_condition": policy.get("vehicle_condition", "Good"),
                "is_blacklisted":   "Yes" if is_blacklisted else "No",
            }
            import numpy as np
            X_r = engine._row(proposal, engine.risk_features)
            acc_prob_val = float(engine.risk_pipeline.predict_proba(X_r)[0, 1])
            risk_score = min(100, max(0, int(acc_prob_val * 100)))
            risk_label = (
                "HIGH"   if acc_prob_val >= 0.5
                else "MEDIUM" if acc_prob_val >= engine.optimal_threshold
                else "LOW"
            )
            acc_prob = round(acc_prob_val * 100, 2)
            explanation = engine.explain(proposal)
    except Exception as ex:
        print(f"ML risk scoring skipped for renewal: {ex}")

    return {
        "policy_id":            req.policy_id,
        "customer_name":        policy["customer_name"],
        "previous_premium":     prev_premium,
        "renewal_premium":      base,
        "premium_change_pct":   round(pct_change, 2),
        "new_ncb":              req.new_ncb,
        "recommendation":       recommendation,
        "risk_factors":         risk_factors,
        "is_blacklisted":       is_blacklisted,
        "blacklist_reason":     bl_status.get("reason") if is_blacklisted else None,
        "claim_summary": {
            "number_of_claims":     number_of_claims,
            "total_claim_amount":   total_claim_amount,
            "highest_claim":        highest_claim,
        },
        # ML risk assessment
        "risk_score":               risk_score,
        "risk_label":               risk_label,
        "accident_probability_pct": acc_prob,
        "explanation":              explanation,
        "breakdown": {
            "previous_premium":     f"Rs.{prev_premium:,.0f}",
            "after_ncb_claims":     f"Rs.{base:,.0f}",
            "si_mv_ratio":          f"{si_ratio:.2f}",
            "years_with_company":   years_co,
        }
    }


# ── GET /policy/{policy_id}  (general lookup) ─────────────────────────────
@router.get("/policy/{policy_id}")
async def get_policy_details(policy_id: str):
    policy = get_policy(policy_id)
    if not policy:
        raise HTTPException(404, detail=f"Policy '{policy_id}' not found")
    claims = get_policy_claims(policy_id)
    bl     = check_blacklist(nic=policy["nic"], policy_id=policy_id)
    return {"policy": policy, "claims": claims, "blacklist": bl}


# ── GET /customer/{nic}/blacklist ─────────────────────────────────────────
@router.get("/customer/{nic}/blacklist")
async def customer_blacklist_check(nic: str):
    return check_blacklist(nic=nic)
