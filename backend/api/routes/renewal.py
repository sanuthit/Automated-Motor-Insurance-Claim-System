
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

    # ── Renewal availability: only open from 11 months after issue/last renewal ──
    from datetime import date as _date
    today_d = _date.today()

    # Prefer policy_end_date; fall back to registration_date + 365
    end_date_str   = (policy.get("policy_end_date") or "").strip()
    start_date_str = (policy.get("policy_start_date") or
                      policy.get("registration_date") or "").strip()

    if end_date_str:
        policy_end = _date.fromisoformat(end_date_str)
    elif start_date_str:
        policy_end = _date.fromisoformat(start_date_str[:10]) + __import__("datetime").timedelta(days=365)
    else:
        policy_end = today_d  # unknown — allow renewal

    # Renewal window: opens 30 days before expiry (= 11 months after start)
    renewal_open  = policy_end - __import__("datetime").timedelta(days=30)
    days_to_open  = (renewal_open - today_d).days
    days_to_expiry = (policy_end - today_d).days

    if today_d < renewal_open:
        raise HTTPException(400, detail=(
            f"Renewal not available yet. "
            f"Policy expires on {policy_end}. "
            f"Renewal window opens on {renewal_open} "
            f"({days_to_open} days from today). "
            f"You can renew from 30 days before expiry."
        ))

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
        "renewal_window": {
            "policy_end_date":   policy_end.isoformat(),
            "renewal_open_date": renewal_open.isoformat(),
            "days_to_expiry":    days_to_expiry,
            "is_open":           True,   # always True here (blocked above if not open)
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
    last_claim_days     = 999
    if claims:
        try:
            from datetime import date as _d
            last_date = _d.fromisoformat(claims[0]["claim_date"])
            last_claim_days = (_d.today() - last_date).days
        except Exception:
            pass

    is_blacklisted = bl_status["blacklisted"]
    si_ratio = req.proposed_sum_insured / max(1, cmv)

    # ── Try ML renewal model first (HistGBR trained on renewal data) ─────
    engine_inst = get_engine()
    renewal_input = {
        "previous_premium":             prev_premium,
        "previous_ncb":                 prev_ncb,
        "new_ncb":                      req.new_ncb,
        "number_of_claims":             number_of_claims,
        "total_claim_amount":           total_claim_amount,
        "highest_claim":                highest_claim,
        "days_since_last_claim":        last_claim_days,
        "vehicle_age":                  policy.get("vehicle_age", 5),
        "driver_age":                   policy.get("driver_age", 35),
        "years_with_company":           years_co,
        "si_mv_ratio":                  si_ratio,
    }
    ml_premium = engine_inst.calculate_renewal_premium(renewal_input)
    risk_factors = []
    premium_source = "ML model"

    if ml_premium is not None:
        # ML model returned a prediction — use it, then apply mandatory overrides
        base = int(ml_premium)
        risk_factors.append(f"ML renewal model prediction: Rs.{base:,.0f}")
        premium_source = "ML renewal model (HistGBM R²={:.3f})".format(
            engine_inst.metadata.get("renewal_model", {}).get("r2_score", 0.0)
        )
    else:
        # ── Rule-based fallback ──────────────────────────────────────────
        base = prev_premium
        premium_source = "Rule-based fallback"
        if number_of_claims == 0:
            ncb_diff = req.new_ncb - prev_ncb
            if ncb_diff > 0:
                base = int(base * (1 - ncb_diff / 100))
                risk_factors.append(f"NCB {prev_ncb:.0f}% → {req.new_ncb:.0f}% (−{ncb_diff:.0f}%)")
        elif number_of_claims == 1:
            loading = 1.35 if highest_claim > 1_000_000 else 1.15
            base = int(base * loading)
            risk_factors.append(f"1 claim: +{int((loading-1)*100)}% loading")
        elif number_of_claims == 2:
            base = int(base * 1.50)
            risk_factors.append("2 claims: +50% loading")
        else:
            base = int(base * 1.80)
            risk_factors.append(f"{number_of_claims} claims: +80% loading")

    # ── Mandatory adjustments applied on top of both ML and rule-based ──
    if is_blacklisted:
        surcharge = engine_inst.actuarial.get("blacklist_surcharge", 0.50)
        base = int(base * (1 + surcharge))
        risk_factors.append(f"Blacklist surcharge +{int(surcharge*100)}%: {bl_status.get('reason','')}")

    if si_ratio > 1.10:
        base = int(base * 1.08)
        risk_factors.append("Over-insured (SI > MV×1.1): +8%")
    elif si_ratio < 0.80:
        base = int(base * 0.95)
        risk_factors.append("Under-insured adjustment: −5%")

    if years_co >= 5 and number_of_claims == 0:
        base = int(base * 0.97)
        risk_factors.append(f"Loyalty discount ({years_co} yrs clean): −3%")

    risk_factors.append(f"Source: {premium_source}")
    base = max(engine_inst.MIN_PREMIUM, base)
    pct_change = (base - prev_premium) / max(1, prev_premium) * 100

    if pct_change < -20 or number_of_claims >= 3 or pct_change > 50:
        recommendation = "REVIEW"
    else:
        recommendation = "APPROVE"

    # ── Risk model — ML if available, rule-based fallback otherwise ──────
    explanation = {"available": False}
    risk_score  = None
    risk_label  = None
    acc_prob    = None
    try:
        engine = get_engine()
        proposal = {
            "driver_age":        policy["driver_age"],
            "years_exp":         policy.get("years_exp", 5),
            "engine_cc":         policy["engine_cc"],
            "vehicle_age":       policy["vehicle_age"],
            "sum_insured":       req.proposed_sum_insured,
            "market_value":      cmv,
            "prev_ncb":          prev_ncb,
            "province":          policy["province"],
            "gender":            policy.get("gender", "Male"),
            "occupation":        policy.get("occupation", "Other"),
            "vehicle_type":      policy.get("vehicle_type", "Car"),
            "vehicle_condition": policy.get("vehicle_condition", "Good"),
            "is_blacklisted":    "Yes" if is_blacklisted else "No",
        }
        if engine.is_ready() and engine.risk_pipeline is not None:
            # ── Step 1: risk probability from ML classifier ──────────────
            inst_vec     = engine._build_row(
                engine._risk_features_dict(proposal), engine.risk_features
            )
            acc_prob_val = float(engine.risk_pipeline.predict_proba(inst_vec)[0, 1])
            risk_score   = min(100, max(0, int(acc_prob_val * 100)))
            risk_label   = (
                "HIGH"   if acc_prob_val >= 0.5
                else "MEDIUM" if acc_prob_val >= engine.optimal_threshold
                else "LOW"
            )
            acc_prob = round(acc_prob_val * 100, 2)

            # ── Step 2: real interventional SHAP via shap_engine ─────────
            shap_eng = getattr(engine, "shap_engine", None)
            if shap_eng and shap_eng.is_ready():
                explanation = shap_eng.compute(inst_vec)
            else:
                explanation = {"available": False, "is_ml_shap": False,
                               "note": "SHAP background not loaded"}
        else:
            risk_score  = 50
            risk_label  = "MEDIUM"
            acc_prob    = 35.0
            explanation = {"available": False, "is_ml_shap": False,
                           "note": "ML model not loaded"}
    except Exception as ex:
        import traceback
        print(f"Risk scoring error for renewal: {ex}\n{traceback.format_exc()}")
        risk_score  = None
        risk_label  = None
        acc_prob    = None
        explanation = {"available": False, "is_ml_shap": False, "error": str(ex)}

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


# ── POST /renewal/process  — finalise renewal, update DB ─────────────────
class RenewalProcessRequest(BaseModel):
    policy_id:            str
    renewal_premium:      float
    new_ncb:              float = 0.0
    proposed_sum_insured: float


@router.post("/renewal/process")
async def process_renewal(req: RenewalProcessRequest):
    """
    Finalise a renewal: update the policies table with new premium,
    new NCB, new policy end date; and insert a row into renewals.
    """
    from backend.utils.database import get_connection
    from datetime import date, timedelta

    policy = get_policy(req.policy_id)
    if not policy:
        raise HTTPException(404, detail=f"Policy '{req.policy_id}' not found")

    today    = date.today()
    end_date = today + timedelta(days=365)

    try:
        with get_connection() as conn:
            # Ensure policy_end_date column exists
            existing = {r[1] for r in conn.execute("PRAGMA table_info(policies)").fetchall()}
            for col, defn in [
                ("policy_start_date", "TEXT DEFAULT ''"),
                ("policy_end_date",   "TEXT DEFAULT ''"),
            ]:
                if col not in existing:
                    try:
                        conn.execute(f"ALTER TABLE policies ADD COLUMN {col} {defn}")
                    except Exception:
                        pass

            # Update policy record
            conn.execute("""
                UPDATE policies
                SET calculated_premium = ?,
                    ncb_pct            = ?,
                    sum_insured        = ?,
                    policy_start_date  = ?,
                    policy_end_date    = ?,
                    status             = 'Active'
                WHERE policy_id = ?
            """, (
                req.renewal_premium,
                req.new_ncb,
                req.proposed_sum_insured,
                today.isoformat(),
                end_date.isoformat(),
                req.policy_id,
            ))

            # Insert renewal record
            last_renewal = conn.execute(
                "SELECT renewal_id FROM renewals ORDER BY renewal_id DESC LIMIT 1"
            ).fetchone()
            digits    = "".join(filter(str.isdigit, str(last_renewal[0]))) if last_renewal else ""
            renewal_id = f"RN{int(digits)+1:08d}" if digits else "RN00000001"

            conn.execute("""
                INSERT OR IGNORE INTO renewals (
                    renewal_id, policy_id, customer_name, renewal_date,
                    driver_age, gender, years_with_company,
                    vehicle_model, vehicle_age,
                    prev_sum_insured, current_market_value, proposed_sum_insured,
                    prev_premium, prev_ncb,
                    new_ncb, renewal_premium,
                    renewal_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                renewal_id, req.policy_id, policy.get("customer_name",""),
                today.isoformat(),
                policy.get("driver_age", 0), policy.get("gender",""),
                1,  # years_with_company placeholder
                policy.get("vehicle_model",""), policy.get("vehicle_age", 0),
                policy.get("sum_insured", 0), policy.get("market_value", 0),
                req.proposed_sum_insured,
                policy.get("calculated_premium", 0), policy.get("ncb_pct", 0),
                req.new_ncb, req.renewal_premium,
                "Renewed",
            ))
            conn.commit()

        # ── Email notification (non-blocking) ──────────────────────────
        email_result = {"sent": False, "error": "not attempted"}
        try:
            from backend.services.email_service import send_renewal_email
            prev_prem = float(policy.get("calculated_premium", req.renewal_premium))
            email_result = send_renewal_email(
                email            = policy.get("email", ""),
                customer_name    = policy.get("customer_name", ""),
                policy_id        = req.policy_id,
                renewal_id       = renewal_id,
                vehicle_model    = policy.get("vehicle_model", ""),
                renewal_premium  = float(req.renewal_premium),
                previous_premium = prev_prem,
                pct_change       = round(
                    (float(req.renewal_premium) - prev_prem) / max(1, prev_prem) * 100, 1
                ),
                new_ncb          = float(req.new_ncb),
                risk_score       = policy.get("risk_score"),
                risk_label       = policy.get("risk_label", ""),
                start_date       = today.isoformat(),
                end_date         = end_date.isoformat(),
                recommendation   = "APPROVE",
            )
        except Exception as _email_err:
            email_result = {"sent": False, "error": str(_email_err)}
            print(f"[Email] renewal notification error: {_email_err}")

        return {
            "success":    True,
            "policy_id":  req.policy_id,
            "renewal_id": renewal_id,
            "start_date": today.isoformat(),
            "end_date":   end_date.isoformat(),
            "message":    f"Policy {req.policy_id} renewed. Valid {today} → {end_date}.",
            "email":      email_result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Renewal failed: {str(e)}")


def _renewal_shap_reasons(p: dict, num_claims: int, risk: int) -> list:
    age  = int(p.get("driver_age", 35))
    exp  = int(p.get("years_exp", 5))
    va   = int(p.get("vehicle_age", 5))
    ncb  = float(p.get("prev_ncb", 0))
    prov = p.get("province", "Western")
    bl   = p.get("is_blacklisted", "No") == "Yes"

    drivers = []
    if bl:
        drivers.append({"feature": "Blacklist Status", "shap_value": 0.32, "direction": "increases_risk",
            "magnitude": "high", "reason": "Blacklisted — high risk surcharge"})
    if num_claims >= 2:
        drivers.append({"feature": "Claims History", "shap_value": 0.28, "direction": "increases_risk",
            "magnitude": "high", "reason": f"{num_claims} claims — significant loading applied"})
    elif num_claims == 1:
        drivers.append({"feature": "Claims History", "shap_value": 0.15, "direction": "increases_risk",
            "magnitude": "medium", "reason": "1 claim — 15–35% loading applied"})
    if age < 25:
        drivers.append({"feature": "Driver Age", "shap_value": 0.22, "direction": "increases_risk",
            "magnitude": "high", "reason": f"Age {age} — young driver loading"})
    elif age > 65:
        drivers.append({"feature": "Driver Age", "shap_value": 0.12, "direction": "increases_risk",
            "magnitude": "medium", "reason": f"Age {age} — senior driver loading"})
    if exp < 3:
        drivers.append({"feature": "Driving Experience", "shap_value": 0.18, "direction": "increases_risk",
            "magnitude": "high", "reason": f"Only {exp} years experience"})
    if va > 12:
        drivers.append({"feature": "Vehicle Age", "shap_value": 0.11, "direction": "increases_risk",
            "magnitude": "medium", "reason": f"Vehicle {va} years old"})
    if ncb >= 20:
        drivers.append({"feature": "NCB Discount", "shap_value": -0.09, "direction": "reduces_risk",
            "magnitude": "medium", "reason": f"{ncb:.0f}% NCB — historically safe driver"})
    if prov == "Western":
        drivers.append({"feature": "Province", "shap_value": 0.07, "direction": "increases_risk",
            "magnitude": "low", "reason": "Western Province — higher claim frequency"})
    if not drivers:
        drivers.append({"feature": "Risk Profile", "shap_value": 0.04,
            "direction": "increases_risk" if risk > 40 else "reduces_risk",
            "magnitude": "low", "reason": "Average risk profile"})
    return drivers[:6]

