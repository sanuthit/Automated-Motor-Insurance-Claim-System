"""
ML Prediction Routes — fixed to match frontend field expectations
"""
from fastapi import APIRouter, HTTPException
from ...utils.schemas import PolicyRequest, PremiumResponse
from ...utils.engine import get_engine
from datetime import date

router = APIRouter()


@router.post("/predict/premium")
async def predict_premium(req: PolicyRequest):
    """
    Calculate risk-based insurance premium.
    Returns full breakdown + SHAP explanation + risk score.
    """
    engine = get_engine()

    vehicle_age = req.vehicle_age if req.vehicle_age is not None else max(0, date.today().year - req.vehicle_year)

    proposal = {
        "driver_age":       req.driver_age,
        "years_exp":        req.years_exp,
        "engine_cc":        req.engine_cc,
        "vehicle_age":      vehicle_age,
        "sum_insured":      req.sum_insured,
        "market_value":     req.market_value,
        "prev_ncb":         req.prev_ncb,
        "gender":           req.gender.value,
        "province":         req.province.value,
        "occupation":       req.occupation,
        "vehicle_type":     req.vehicle_type.value,
        "vehicle_condition": req.vehicle_condition.value,
        "is_blacklisted":   "Yes" if req.is_blacklisted else "No",
        "rebate_approved":  "Yes" if req.rebate_approved else "No",
        "images":           "Yes" if req.images else "No",
        "inspection":       "Yes" if req.inspection else "No",
        "reg_book":         "Yes" if req.reg_book else "No",
        "fair_value":       "Yes" if req.fair_value else "No",
        "financial_interest": "Yes" if req.financial_interest else "No",
    }

    if not engine.is_ready():
        # ── Fallback: deterministic premium when models not loaded ─────────
        result = _deterministic_premium(proposal)
    else:
        try:
            result = engine.calculate(proposal)
            # Engine doesn't return base_premium — compute it from net + NCB
            if "base_premium" not in result:
                net = result.get("net_premium", 0)
                ncb_pct = float(proposal.get("prev_ncb", 0))
                # Reverse: net = base * (1 - ncb/100), so base = net / (1 - ncb/100)
                denom = (1 - ncb_pct / 100) if ncb_pct < 100 else 1
                result["base_premium"]  = int(net / denom) if denom > 0 else int(net)
                result["ncb_discount"]  = result["base_premium"] - int(net)
        except Exception as e:
            # Still return something useful rather than 500
            result = _deterministic_premium(proposal)
            result["engine_error"] = str(e)

    # Ensure all required fields exist
    result.setdefault("risk_score", 50)
    result.setdefault("accident_probability_pct", 33.0)
    result.setdefault("risk_label", "MEDIUM")
    result.setdefault("is_insurable", True)
    result.setdefault("doc_complete", True)
    result.setdefault("ncb_pct", float(req.prev_ncb))
    result.setdefault("breakdown", {})

    # Always ensure explanation is populated — rule-based fallback if ML not available
    if not result.get("explanation", {}).get("available"):
        result["explanation"] = {
            "available": True,
            "is_ml_shap": False,
            "note": "Rule-based explanation — train ML pipeline for real SHAP values",
            "top_drivers": _build_shap_reasons(proposal, result.get("risk_score", 50)),
        }

    return result


def _deterministic_premium(p: dict) -> dict:
    """
    Rule-based fallback premium when ML models are not yet trained.
    Uses real Sri Lanka rates: 3%–5.5% of SI.
    """
    si  = float(p.get("sum_insured", 1_000_000))
    mv  = float(p.get("market_value", si))
    age = int(p.get("driver_age", 35))
    exp = int(p.get("years_exp", 5))
    cc  = int(p.get("engine_cc", 1500))
    vt  = p.get("vehicle_type", "Car")
    va  = int(p.get("vehicle_age", 5))
    ncb = int(p.get("prev_ncb", 0))
    prov= p.get("province", "Western")
    bl  = p.get("is_blacklisted", "No") == "Yes"
    cond= p.get("vehicle_condition", "Good")

    # Base rate by vehicle type + CC
    if vt in ("SUV", "Dual Purpose"):
        rate = 0.048
    elif vt == "Van":
        rate = 0.045
    elif cc > 2500:
        rate = 0.052
    elif cc > 1800:
        rate = 0.044
    else:
        rate = 0.038

    # Age loading
    if age < 22:    rate += 0.018
    elif age < 26:  rate += 0.010
    elif age > 65:  rate += 0.008

    # Experience discount
    if exp > 15:    rate -= 0.006
    elif exp < 3:   rate += 0.010

    # Vehicle age loading
    if va > 12:     rate += 0.010
    elif va > 8:    rate += 0.005

    # Province
    if prov == "Western":  rate += 0.006
    elif prov == "Southern": rate += 0.003

    # Condition
    if cond == "Poor":    rate += 0.012
    elif cond == "Fair":  rate += 0.006

    # Blacklist surcharge
    if bl: rate += 0.020

    # Caps
    rate = max(0.030, min(0.060, rate))

    base = int(si * rate)
    ncb_discount = int(base * ncb / 100)
    net = base - ncb_discount
    stamp = int(net * 0.010)
    vat   = int(net * 0.080)
    cess  = int(net * 0.005)
    gross = net + stamp + vat + cess

    # Risk score
    risk = 30
    if age < 25:  risk += 22
    elif age > 65: risk += 12
    if exp < 3:   risk += 18
    if va > 12:   risk += 10
    if cc > 2500: risk += 8
    if prov == "Western": risk += 6
    if bl:        risk += 25
    risk -= int(ncb * 0.3)
    risk = max(5, min(95, risk))

    label = "HIGH" if risk >= 70 else "MEDIUM" if risk >= 40 else "LOW"

    return {
        "risk_score":               risk,
        "accident_probability_pct": round(risk * 0.7, 1),
        "risk_label":               label,
        "base_premium":             base,
        "ncb_discount":             ncb_discount,
        "net_premium":              net,
        "stamp_duty":               stamp,
        "vat":                      vat,
        "cess":                     cess,
        "gross_premium":            gross,
        "ncb_pct":                  float(ncb),
        "rate_pct":                 round(rate, 4),
        "is_insurable":             not bl or risk < 90,
        "doc_complete":             True,
        "breakdown": {
            "base_rate_pct":    f"{rate*100:.2f}%",
            "sum_insured":      f"Rs.{si:,.0f}",
            "ncb_discount":     f"Rs.{ncb_discount:,.0f}",
            "net_premium":      f"Rs.{net:,.0f}",
            "stamp_duty":       f"Rs.{stamp:,.0f}",
            "vat_8pct":         f"Rs.{vat:,.0f}",
            "cess_0_5pct":      f"Rs.{cess:,.0f}",
            "gross":            f"Rs.{gross:,.0f}",
            "note":             "Deterministic fallback — train ML models for AI-driven rates",
        },
        "explanation": {
            "available": True,
            "is_ml_shap": False,
            "note": "Rule-based explanation — train ML pipeline for real SHAP values",
            "top_drivers": _build_shap_reasons(p, risk),
        }
    }


def _build_shap_reasons(p: dict, risk: int) -> list:
    age = int(p.get("driver_age", 35))
    exp = int(p.get("years_exp", 5))
    va  = int(p.get("vehicle_age", 5))
    cc  = int(p.get("engine_cc", 1500))
    ncb = int(p.get("prev_ncb", 0))
    prov= p.get("province", "Western")
    bl  = p.get("is_blacklisted", "No") == "Yes"

    drivers = []

    if bl:
        drivers.append({"feature": "Blacklist Status", "shap_value": 0.32,
            "direction": "increases_risk", "magnitude": "high",
            "reason": "Blacklisted — high risk surcharge"})
    if age < 22:
        drivers.append({"feature": "Driver Age", "shap_value": 0.22,
            "direction": "increases_risk", "magnitude": "high",
            "reason": f"Age {age} — very young driver, high accident rate"})
    elif age < 26:
        drivers.append({"feature": "Driver Age", "shap_value": 0.14,
            "direction": "increases_risk", "magnitude": "medium",
            "reason": f"Age {age} — young driver loading"})
    elif age > 65:
        drivers.append({"feature": "Driver Age", "shap_value": 0.12,
            "direction": "increases_risk", "magnitude": "medium",
            "reason": f"Age {age} — senior driver loading"})
    if exp < 3:
        drivers.append({"feature": "Driving Experience", "shap_value": 0.18,
            "direction": "increases_risk", "magnitude": "high",
            "reason": f"Only {exp} years experience — high risk"})
    elif exp > 15:
        drivers.append({"feature": "Driving Experience", "shap_value": -0.08,
            "direction": "reduces_risk", "magnitude": "medium",
            "reason": f"{exp} years experience — experienced driver discount"})
    if va > 12:
        drivers.append({"feature": "Vehicle Age", "shap_value": 0.11,
            "direction": "increases_risk", "magnitude": "high",
            "reason": f"Vehicle {va} years old — higher mechanical risk"})
    if prov == "Western":
        drivers.append({"feature": "Province", "shap_value": 0.07,
            "direction": "increases_risk", "magnitude": "medium",
            "reason": "Western Province — higher traffic density & claim frequency"})
    if ncb >= 20:
        drivers.append({"feature": "NCB Discount", "shap_value": -0.09,
            "direction": "reduces_risk", "magnitude": "medium",
            "reason": f"{ncb}% NCB — historically safe driver"})
    if cc > 2500:
        drivers.append({"feature": "Engine CC", "shap_value": 0.08,
            "direction": "increases_risk", "magnitude": "medium",
            "reason": f"{cc}cc — high-performance engine, higher repair cost"})

    # Default if nothing significant
    if not drivers:
        drivers.append({"feature": "Risk Profile", "shap_value": 0.04,
            "direction": "increases_risk" if risk > 40 else "reduces_risk",
            "magnitude": "low", "reason": "Average risk profile"})

    return drivers[:7]


@router.post("/predict/risk-only")
async def predict_risk_only(req: dict):
    """Quick risk score estimation."""
    engine = get_engine()
    try:
        if engine.is_ready():
            X_r = engine._row(req, engine.risk_features)
            acc_prob = float(engine.risk_pipeline.predict_proba(X_r)[0, 1])
        else:
            age, exp = int(req.get("driver_age", 35)), int(req.get("years_exp", 5))
            acc_prob = 0.12 + (0.22 if age < 25 else 0) + (0.14 if exp < 3 else -0.04 if exp > 15 else 0)
            acc_prob = max(0.05, min(0.90, acc_prob))

        risk_score = min(100, max(0, int(acc_prob * 100)))
        return {
            "risk_score": risk_score,
            "accident_probability_pct": round(acc_prob * 100, 2),
            "risk_label": "HIGH" if risk_score >= 70 else "MEDIUM" if risk_score >= 40 else "LOW",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Vehicle catalogue — live from DB, no hardcoding
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/vehicles/models")
async def get_vehicle_models():
    """Distinct models + most-common vehicle_type from policies table. Motor Cycle excluded."""
    try:
        from ...utils.database import get_connection
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT vehicle_model, vehicle_type, COUNT(*) AS cnt
                FROM   policies
                WHERE  vehicle_model IS NOT NULL AND vehicle_model != ''
                  AND  vehicle_type  NOT IN ('Motor Cycle', '')
                GROUP  BY vehicle_model, vehicle_type
                ORDER  BY vehicle_model, cnt DESC
            """).fetchall()
        seen = {}
        for r in rows:
            m, t = str(r[0]).strip(), str(r[1]).strip()
            if m and m not in seen:
                seen[m] = t
        models = [{"model": k, "vehicle_type": v} for k, v in sorted(seen.items())]
        return {"models": models, "total": len(models)}
    except Exception as e:
        return {"models": [], "total": 0, "error": str(e)}


@router.get("/vehicles/types")
async def get_vehicle_types():
    """Vehicle types in DB — Motor Cycle excluded."""
    try:
        from ...utils.database import get_connection
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT DISTINCT vehicle_type, COUNT(*) AS cnt
                FROM   policies
                WHERE  vehicle_type IS NOT NULL
                  AND  vehicle_type NOT IN ('Motor Cycle', '')
                GROUP  BY vehicle_type ORDER BY cnt DESC
            """).fetchall()
        return {"types": [str(r[0]) for r in rows]}
    except Exception as e:
        return {"types": ["Car", "SUV", "Van", "Dual Purpose"], "error": str(e)}


@router.post("/policy/issue")
async def issue_policy(req: dict):
    """
    Persist a newly issued policy.  Auto-generates policy_id (NP00060001 …).
    Safely migrates any missing extra columns via ALTER TABLE.
    59 columns and 59 values — verified by assertion.
    """
    try:
        from ...utils.database import get_connection
        from datetime import date, timedelta

        today    = date.today()
        end_date = today + timedelta(days=365)

        with get_connection() as conn:

            # ── next policy ID ────────────────────────────────────────────
            row = conn.execute(
                "SELECT policy_id FROM policies ORDER BY policy_id DESC LIMIT 1"
            ).fetchone()
            digits    = "".join(filter(str.isdigit, str(row[0]))) if row else ""
            policy_id = f"NP{int(digits)+1:08d}" if digits else "NP00000001"

            # ── safe column migration ─────────────────────────────────────
            existing = {r[1] for r in conn.execute("PRAGMA table_info(policies)").fetchall()}
            for col, defn in [
                ("telephone",               "TEXT DEFAULT ''"),
                ("address",                 "TEXT DEFAULT ''"),
                ("email",                   "TEXT DEFAULT ''"),
                ("vat_no",                  "TEXT DEFAULT ''"),
                ("business_reg_no",         "TEXT DEFAULT ''"),
                ("auto_association_member", "TEXT DEFAULT 'No'"),
                ("accident_last_3yrs",      "INTEGER DEFAULT 0"),
                ("garaged_address",         "TEXT DEFAULT ''"),
                ("used_for",                "TEXT DEFAULT 'Domestic and private purpose'"),
                ("cover_type",              "TEXT DEFAULT 'Comprehensive'"),
                ("accessories_value",       "REAL DEFAULT 0"),
                ("policy_start_date",       "TEXT DEFAULT ''"),
                ("policy_end_date",         "TEXT DEFAULT ''"),
                ("reg_number",              "TEXT DEFAULT ''"),
                ("colour",                  "TEXT DEFAULT ''"),
                ("chassis_no",              "TEXT DEFAULT ''"),
                ("seating_capacity",        "TEXT DEFAULT ''"),
                ("is_duty_free",            "TEXT DEFAULT 'No'"),
                ("has_lpg",                 "TEXT DEFAULT 'No'"),
                ("cover_strike_riot",       "TEXT DEFAULT 'No'"),
                ("cover_terrorism",         "TEXT DEFAULT 'No'"),
                ("cover_personal_accident", "TEXT DEFAULT 'No'"),
                ("cover_windscreen",        "TEXT DEFAULT 'No'"),
                ("cover_flood",             "TEXT DEFAULT 'No'"),
                ("cover_towing",            "TEXT DEFAULT 'No'"),
                ("cover_learner",           "TEXT DEFAULT 'No'"),
                ("cover_workmen_comp",      "TEXT DEFAULT 'No'"),
            ]:
                if col not in existing:
                    try:
                        conn.execute(f"ALTER TABLE policies ADD COLUMN {col} {defn}")
                    except Exception:
                        pass

            vehicle_year = int(req.get("vehicle_year", today.year))
            vehicle_age  = max(0, today.year - vehicle_year)
            yn = lambda k: "Yes" if req.get(k) else "No"

            # 59 columns
            col_list = (
                "policy_id,registration_date,"
                "customer_name,nic,driver_age,gender,occupation,"
                "years_exp,province,city,"
                "vehicle_model,vehicle_year,vehicle_age,engine_cc,"
                "vehicle_type,market_value,sum_insured,"
                "vehicle_condition,previous_insurer,"
                "is_existing_customer,is_blacklisted,"
                "images,inspection,fair_value,financial_interest,"
                "reg_book,ncb_pct,valid_renewal_notice,rebate_approved,"
                "risk_score,calculated_premium,status,"
                "telephone,address,email,vat_no,business_reg_no,"
                "auto_association_member,accident_last_3yrs,"
                "garaged_address,used_for,cover_type,accessories_value,"
                "policy_start_date,policy_end_date,"
                "reg_number,colour,chassis_no,seating_capacity,"
                "is_duty_free,has_lpg,"
                "cover_strike_riot,cover_terrorism,cover_personal_accident,"
                "cover_windscreen,cover_flood,cover_towing,"
                "cover_learner,cover_workmen_comp"
            )
            # 59 values — same order as col_list
            vals = (
                policy_id,                        today.isoformat(),
                req.get("customer_name", ""),     req.get("nic", ""),
                int(req.get("driver_age", 30)),   req.get("gender", "Male"),
                req.get("occupation", "Employed"),
                int(req.get("years_exp", 0)),     req.get("province", "Western"),
                req.get("city", ""),
                req.get("vehicle_model", ""),     vehicle_year,
                vehicle_age,                      int(req.get("engine_cc", 1000)),
                req.get("vehicle_type", "Car"),   float(req.get("market_value", 0)),
                float(req.get("sum_insured", 0)), req.get("vehicle_condition", "Good"),
                req.get("previous_insurer", ""),
                yn("is_existing_customer"),        yn("is_blacklisted"),
                yn("images"),                      yn("inspection"),
                yn("fair_value"),                  yn("financial_interest"),
                yn("reg_book"),                    float(req.get("prev_ncb", 0)),
                yn("valid_renewal_notice"),         yn("rebate_approved"),
                int(req.get("risk_score", 50)),   float(req.get("gross_premium", 0)),
                "Active",
                req.get("telephone", ""),          req.get("address", ""),
                req.get("email", ""),              req.get("vat_no", ""),
                req.get("business_reg_no", ""),
                yn("auto_association_member"),     int(req.get("accident_last_3yrs", 0)),
                req.get("garaged_address", ""),    req.get("used_for", "Domestic and private purpose"),
                req.get("cover_type", "Comprehensive"),
                float(req.get("accessories_value", 0)),
                today.isoformat(),                 end_date.isoformat(),
                req.get("reg_number", ""),         req.get("colour", ""),
                req.get("chassis_no", ""),          str(req.get("seating_capacity", "")),
                yn("is_duty_free"),                yn("has_lpg"),
                yn("strike_riot"),                 yn("terrorism_cover"),
                yn("personal_accident"),           yn("windscreen_cover"),
                yn("flood_cover"),                 yn("towing_cover"),
                yn("learner_driver"),              yn("workmen_comp"),
            )

            nc = len(col_list.split(","))
            assert nc == len(vals), f"cols={nc} vals={len(vals)}"
            placeholders = ",".join("?" * nc)
            conn.execute(
                f"INSERT OR IGNORE INTO policies ({col_list}) VALUES ({placeholders})",
                vals
            )
            conn.commit()

        return {
            "success":    True,
            "policy_id":  policy_id,
            "start_date": today.isoformat(),
            "end_date":   end_date.isoformat(),
            "message":    f"Policy {policy_id} issued. Valid {today} to {end_date}.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to issue policy: {str(e)}")


@router.get("/policies/list")
async def list_policies_for_dropdown():
    """Return policy IDs + customer names for renewal dropdown search."""
    try:
        from backend.utils.database import get_connection
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT policy_id, customer_name, vehicle_model, driver_age, province, status
                FROM policies
                WHERE status = 'Active'
                ORDER BY policy_id DESC
                LIMIT 500
            """).fetchall()
        return {
            "policies": [
                {
                    "policy_id":     r[0],
                    "customer_name": r[1] or "",
                    "vehicle_model": r[2] or "",
                    "driver_age":    r[3],
                    "province":      r[4] or "",
                    "status":        r[5] or "Active",
                }
                for r in rows
            ]
        }
    except Exception as e:
        return {"policies": [], "error": str(e)}
