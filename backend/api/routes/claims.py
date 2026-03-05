"""
Claims Management Routes — fixed field names to match ClaimRequest schema
"""
from fastapi import APIRouter, HTTPException
from ...utils.schemas import ClaimRequest, ClaimResponse
import uuid
from datetime import datetime

router = APIRouter()
_claims = {}

CLAIM_DEDUCTIBLES = {
    "Accidental Damage":     0.05,
    "Third Party Liability": 0.03,
    "Windscreen Damage":     0.02,
    "Theft of Parts":        0.07,
    "Theft of Vehicle":      0.10,
    "Fire Damage":           0.05,
    "Flood / Natural Disaster": 0.08,
    "Own Damage":            0.05,
    "Other":                 0.05,
}

PROCESSING_DAYS = {
    "Approved":               3,
    "Pending Review":        14,
    "Requires Investigation":30,
}


@router.post("/claim/submit")
@router.post("/claims/submit")   # support both URL patterns
async def submit_claim(req: ClaimRequest):
    claim_id  = f"CLM{uuid.uuid4().hex[:8].upper()}"
    risk_flags = []
    risk_score = None

    claim_amount = req.claim_amount or 0
    insured_value = req.insured_value or 0

    # ── Risk flags ────────────────────────────────────────────────────────────
    if req.driver_age and req.driver_age < 25:
        risk_flags.append("Young driver (<25 yrs)")
    if req.previous_claims and req.previous_claims >= 3:
        risk_flags.append("High claim history (3+ previous claims)")
    if insured_value and claim_amount > insured_value * 0.8:
        risk_flags.append("Claim >80% of insured value — total loss suspected")
    if req.at_fault is True:
        risk_flags.append("At-fault accident")
    if claim_amount > 5_000_000:
        risk_flags.append("High-value claim — requires senior adjuster review")
    if req.claim_type == "Theft of Vehicle" and not req.police_report_available:
        risk_flags.append("No police report for theft claim")
    if req.accident_severity in ("Severe", "Total Loss"):
        risk_flags.append(f"Accident severity: {req.accident_severity}")

    # ── Status ────────────────────────────────────────────────────────────────
    if insured_value and claim_amount > insured_value:
        status = "Requires Investigation"
        approved_pct = 0.0
    elif len(risk_flags) >= 3:
        status = "Requires Investigation"
        approved_pct = 0.0
    elif len(risk_flags) >= 2:
        status = "Pending Review"
        approved_pct = 0.80
    else:
        status = "Approved"
        approved_pct = 1.0

    ded_rate = CLAIM_DEDUCTIBLES.get(req.claim_type, 0.05)
    deductible      = int(claim_amount * ded_rate)
    approved_amount = int(max(0, claim_amount - deductible) * approved_pct)

    # ── Simple risk score ─────────────────────────────────────────────────────
    risk = 20
    if req.driver_age:
        if req.driver_age < 25: risk += 20
        elif req.driver_age > 65: risk += 12
    if req.vehicle_age and req.vehicle_age > 10: risk += 8
    risk += min(30, len(risk_flags) * 10)
    risk = max(5, min(95, risk))

    note = "Auto-approved — no significant risk flags"
    if risk_flags:
        note = f"Risk flags: {', '.join(risk_flags[:2])}"

    record = {
        "claim_id":          claim_id,
        "claim_status":      status,
        "approved_amount":   approved_amount,
        "deductible":        deductible,
        "recommendation":    "Auto-approved" if status == "Approved" and not risk_flags
                             else f"Review required: {', '.join(risk_flags[:2])}",
        "risk_flags":        risk_flags,
        "risk_score":        risk,
        "risk_note":         note,
        "processing_days":   PROCESSING_DAYS.get(status, 7),
        "claim_date":        datetime.now().isoformat(),
        "claim_type":        req.claim_type,
        "claim_amount":      claim_amount,
        "policy_number":     req.policy_number,
    }
    _claims[claim_id] = record
    return record


@router.get("/claims")
async def list_claims(status: str = None):
    claims = list(_claims.values())
    if status:
        claims = [c for c in claims if c["claim_status"] == status]
    return {"total": len(claims), "claims": claims}


@router.get("/claim/{claim_id}")
async def get_claim(claim_id: str):
    if claim_id not in _claims:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _claims[claim_id]
