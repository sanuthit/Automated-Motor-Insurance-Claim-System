from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date, timedelta
import sqlite3, json
from pathlib import Path

# ── adjust import path to match your project structure ────────────────────
from backend.utils.database import get_connection, get_config
from backend.utils.engine import get_engine

router = APIRouter(prefix="/api/v1", tags=["policy"])


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

class NewPolicyRequest(BaseModel):
    # Proposer Info
    customer_name:              str
    nic:                        str
    driver_age:                 int
    gender:                     str
    occupation:                 str
    years_experience:           int
    province:                   str
    city:                       str
    # Vehicle & Coverage
    vehicle_model:              str
    vehicle_year:               int
    vehicle_age:                int
    engine_cc:                  int
    vehicle_type:               str
    vehicle_condition:          str
    market_value:               float
    proposed_sum_insured:       float
    ncb_pct:                    float = 0
    is_existing_customer:       bool  = False
    is_blacklisted:             bool  = False
    previous_insurer:           str   = ""
    images_uploaded:            bool  = True
    inspection_uploaded:        bool  = True
    fair_value_proposed:        bool  = True
    reg_book_available:         bool  = True
    financial_interest:         bool  = False
    valid_renewal_notice:       bool  = False
    rebate_approved:            bool  = False
    # Calculated by engine (passed from frontend after Step 3)
    risk_score:                 int   = 50
    calculated_premium:         float = 0
    net_premium:                float = 0


class RenewalProcessRequest(BaseModel):
    policy_id:                  str
    proposed_sum_insured:       float
    new_ncb:                    float
    renewal_premium:            float
    net_premium:                float
    # updated claim info from DB (pass back what was shown)
    number_of_claims:           int   = 0
    total_claim_amount:         float = 0
    highest_claim:              float = 0
    premium_change_pct:         float = 0
    renewal_status:             str   = "Accepted"


class SIPredictRequest(BaseModel):
    vehicle_model:  str
    vehicle_age:    int
    vehicle_type:   str
    market_value:   Optional[float] = None


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _next_policy_id(conn) -> str:
    """Generate next NP* policy ID."""
    row = conn.execute(
        "SELECT Policy_ID FROM policies ORDER BY Policy_ID DESC LIMIT 1"
    ).fetchone()
    if not row:
        return "NP00000001"
    last = row[0]  # e.g. "NP00033493"
    num  = int(last[2:]) + 1
    return f"NP{num:08d}"


def _next_renewal_id(conn) -> str:
    row = conn.execute(
        "SELECT renewal_id FROM renewals ORDER BY renewal_id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return "RN00000001"
    num = int(row[0][2:]) + 1
    return f"RN{num:08d}"


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/policy/issue")
def issue_new_policy(req: NewPolicyRequest):
    today      = date.today()
    start_date = today.isoformat()
    end_date   = (today + timedelta(days=365)).isoformat()

    with get_connection() as conn:
        policy_id = _next_policy_id(conn)

        conn.execute("""
            INSERT INTO policies (
                policy_id, registration_date, customer_name, nic,
                driver_age, gender, occupation, years_of_driving_experience,
                province, city, vehicle_model, vehicle_year, vehicle_age_years,
                engine_cc, vehicle_type, market_value_lkr,
                proposed_sum_insured_lkr, suggested_si_lkr,
                suggested_si_min_lkr, suggested_si_max_lkr,
                previous_insurer, vehicle_condition,
                is_existing_customer, is_blacklisted,
                images_uploaded, inspection_report_uploaded,
                fair_value_proposed, financial_interest_recorded,
                registration_book_available, ncb_claimed_percentage,
                valid_renewal_notice, rebate_approved,
                risk_score, calculated_premium_lkr, net_premium_lkr,
                policy_start_date, policy_end_date, status
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
        """, (
            policy_id,
            today.isoformat(),
            req.customer_name,
            req.nic,
            req.driver_age,
            req.gender,
            req.occupation,
            req.years_experience,
            req.province,
            req.city,
            req.vehicle_model,
            req.vehicle_year,
            req.vehicle_age,
            req.engine_cc,
            req.vehicle_type,
            req.market_value,
            req.proposed_sum_insured,
            req.market_value,                       # suggested = market value
            int(req.market_value * 0.90),
            int(req.market_value * 1.10),
            req.previous_insurer,
            req.vehicle_condition,
            "Yes" if req.is_existing_customer else "No",
            "Yes" if req.is_blacklisted else "No",
            "Yes" if req.images_uploaded else "No",
            "Yes" if req.inspection_uploaded else "No",
            "Yes" if req.fair_value_proposed else "No",
            "Yes" if req.financial_interest else "No",
            "Yes" if req.reg_book_available else "No",
            req.ncb_pct,
            "Yes" if req.valid_renewal_notice else "No",
            "Yes" if req.rebate_approved else "No",
            req.risk_score,
            req.calculated_premium,
            req.net_premium,
            start_date,
            end_date,
            "Active",
        ))
        conn.commit()

    return {
        "success":     True,
        "policy_id":   policy_id,
        "start_date":  start_date,
        "end_date":    end_date,
        "message":     f"Policy {policy_id} issued successfully. Valid {start_date} → {end_date}.",
    }


@router.post("/renewal/process")
def process_renewal(req: RenewalProcessRequest):
    
    today      = date.today()
    start_date = today.isoformat()
    end_date   = (today + timedelta(days=365)).isoformat()

    with get_connection() as conn:
        # Check policy exists
        row = conn.execute(
            "SELECT * FROM policies WHERE policy_id = ?", (req.policy_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Policy {req.policy_id} not found")

        # Get column names
        cols = [d[0] for d in conn.execute("SELECT * FROM policies LIMIT 0").description]
        pol  = dict(zip(cols, row))

        # Update policy table: new SI, premium, NCB, dates, status = Active
        conn.execute("""
            UPDATE policies SET
                proposed_sum_insured_lkr  = ?,
                ncb_claimed_percentage    = ?,
                calculated_premium_lkr    = ?,
                net_premium_lkr           = ?,
                policy_start_date         = ?,
                policy_end_date           = ?,
                status                    = 'Active',
                vehicle_age_years         = vehicle_age_years + 1
            WHERE policy_id = ?
        """, (
            req.proposed_sum_insured,
            req.new_ncb,
            req.renewal_premium,
            req.net_premium,
            start_date,
            end_date,
            req.policy_id,
        ))

        # Insert renewal history record
        ren_id = _next_renewal_id(conn)
        conn.execute("""
            INSERT INTO renewals (
                renewal_id, policy_id, customer_name, renewal_date,
                driver_age, gender, years_with_company,
                vehicle_model, vehicle_age,
                prev_sum_insured, current_market_value, proposed_sum_insured,
                prev_premium, prev_ncb,
                claims_last_year, number_of_claims,
                total_claim_amount, highest_claim_amount,
                days_since_last_claim, new_ncb,
                renewal_premium, premium_change_pct, renewal_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ren_id,
            req.policy_id,
            pol.get("customer_name",""),
            today.isoformat(),
            pol.get("driver_age", 0),
            pol.get("gender",""),
            # years_with_company = count previous renewals + 1
            conn.execute(
                "SELECT COUNT(*) FROM renewals WHERE policy_id=?", (req.policy_id,)
            ).fetchone()[0] + 1,
            pol.get("vehicle_model",""),
            int(pol.get("vehicle_age_years", 0)) + 1,
            pol.get("proposed_sum_insured_lkr", 0),
            pol.get("market_value_lkr", 0),
            req.proposed_sum_insured,
            pol.get("calculated_premium_lkr", 0),
            pol.get("ncb_claimed_percentage", 0),
            req.number_of_claims,
            req.number_of_claims,
            req.total_claim_amount,
            req.highest_claim,
            999 if req.number_of_claims == 0 else 180,
            req.new_ncb,
            req.renewal_premium,
            req.premium_change_pct,
            req.renewal_status,
        ))
        conn.commit()

    return {
        "success":     True,
        "policy_id":   req.policy_id,
        "renewal_id":  ren_id,
        "start_date":  start_date,
        "end_date":    end_date,
        "new_si":      req.proposed_sum_insured,
        "new_ncb":     req.new_ncb,
        "new_premium": req.renewal_premium,
        "message":     f"Policy {req.policy_id} renewed. Valid {start_date} → {end_date}.",
    }


@router.post("/predict/si")
def predict_si(req: SIPredictRequest):
    """
    Predict SI for new policy or renewal without user input.
    Returns suggested, min, and max SI based on vehicle characteristics.
    """
    engine = get_engine()
    result = engine.predict_si({
        "vehicle_model":  req.vehicle_model,
        "vehicle_age":    req.vehicle_age,
        "vehicle_type":   req.vehicle_type,
        "market_value":   req.market_value or 0,
    })
    return result


@router.get("/dashboard/stats")
def dashboard_stats(
    province:     Optional[str] = None,
    vehicle_type: Optional[str] = None,
    date_from:    Optional[str] = None,
    date_to:      Optional[str] = None,
    risk_level:   Optional[str] = None,    # LOW / MEDIUM / HIGH
):
    """
    Dashboard statistics with optional filters.
    All filters are optional — omit to see overall stats.
    """
    with get_connection() as conn:
        # Base WHERE clauses
        where = ["1=1"]
        params = []
        if province:
            where.append("province = ?"); params.append(province)
        if vehicle_type:
            where.append("vehicle_type = ?"); params.append(vehicle_type)
        if date_from:
            where.append("registration_date >= ?"); params.append(date_from)
        if date_to:
            where.append("registration_date <= ?"); params.append(date_to)
        if risk_level == "HIGH":
            where.append("risk_score >= 65")
        elif risk_level == "MEDIUM":
            where.append("risk_score BETWEEN 35 AND 64")
        elif risk_level == "LOW":
            where.append("risk_score < 35")

        w = " AND ".join(where)

        total     = conn.execute(f"SELECT COUNT(*) FROM policies WHERE {w}", params).fetchone()[0]
        active    = conn.execute(f"SELECT COUNT(*) FROM policies WHERE {w} AND status='Active'", params).fetchone()[0]
        avg_prem  = conn.execute(f"SELECT AVG(calculated_premium_lkr) FROM policies WHERE {w} AND calculated_premium_lkr>0", params).fetchone()[0]
        high_risk = conn.execute(f"SELECT COUNT(*) FROM policies WHERE {w} AND risk_score>=65", params).fetchone()[0]
        blacklist = conn.execute(f"SELECT COUNT(*) FROM policies WHERE {w} AND is_blacklisted='Yes'", params).fetchone()[0]

        # Claims stats (no province filter on claims table — join needed)
        claim_params = list(params)
        claim_where  = w.replace("registration_date", "p.registration_date")  # alias if needed
        total_claims  = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        total_claim_amount = conn.execute("SELECT SUM(claim_amount_lkr) FROM claims WHERE claim_status='Approved'").fetchone()[0] or 0
        avg_claim    = conn.execute("SELECT AVG(claim_amount_lkr) FROM claims WHERE claim_status='Approved'").fetchone()[0] or 0

        # Renewal count
        renewals = conn.execute("SELECT COUNT(*) FROM renewals").fetchone()[0]

        # Province breakdown
        prov_data = conn.execute(
            f"SELECT province, COUNT(*) as cnt, AVG(risk_score) as avg_risk FROM policies WHERE {w} GROUP BY province ORDER BY cnt DESC",
            params
        ).fetchall()

        # Vehicle type breakdown
        vt_data = conn.execute(
            f"SELECT vehicle_type, COUNT(*) as cnt, AVG(calculated_premium_lkr) as avg_prem FROM policies WHERE {w} GROUP BY vehicle_type ORDER BY cnt DESC",
            params
        ).fetchall()

        # Monthly new policies (last 12 months)
        monthly = conn.execute(
            f"""SELECT substr(registration_date,1,7) as month, COUNT(*) as cnt
                FROM policies WHERE {w} AND registration_date >= date('now','-12 months')
                GROUP BY month ORDER BY month""",
            params
        ).fetchall()

        # NCB distribution
        ncb_dist = conn.execute(
            f"SELECT ncb_claimed_percentage, COUNT(*) FROM policies WHERE {w} GROUP BY ncb_claimed_percentage ORDER BY ncb_claimed_percentage",
            params
        ).fetchall()

    return {
        "summary": {
            "total_policies":      total,
            "active_policies":     active,
            "total_renewals":      renewals,
            "total_claims":        total_claims,
            "blacklisted_count":   blacklist,
            "high_risk_count":     high_risk,
            "avg_premium_lkr":     round(avg_prem or 0, 0),
            "total_claim_paid_lkr": round(total_claim_amount, 0),
            "avg_claim_lkr":       round(avg_claim, 0),
        },
        "by_province":    [{"province": r[0], "count": r[1], "avg_risk": round(r[2] or 0, 1)} for r in prov_data],
        "by_vehicle_type":[{"type": r[0], "count": r[1], "avg_premium": round(r[2] or 0, 0)} for r in vt_data],
        "monthly_trend":  [{"month": r[0], "new_policies": r[1]} for r in monthly],
        "ncb_distribution":[{"ncb": r[0], "count": r[1]} for r in ncb_dist],
        "filters_applied": {
            "province":     province,
            "vehicle_type": vehicle_type,
            "date_from":    date_from,
            "date_to":      date_to,
            "risk_level":   risk_level,
        }
    }


# ── Register in main.py ────────────────────────────────────────────────────
# In backend/api/main.py, add:
#
#   from api.routes.db_update_routes import router as db_router
#   app.include_router(db_router)
#
# ── Frontend: add to api.js ───────────────────────────────────────────────
#   issueNewPolicy:   (data) => api.post('/policy/issue', data),
#   processRenewal:   (data) => api.post('/renewal/process', data),
#   predictSI:        (data) => api.post('/predict/si', data),
#   getDashboardStats:(params) => api.get('/dashboard/stats', { params }),
#
# ── NewPolicy.jsx: call issueNewPolicy on "Issue Policy" button click ─────
#   const handleIssuePolicy = async () => {
#     const payload = { ...proposerInfo, ...vehicleInfo, ...riskResult };
#     const res = await insuranceAPI.issueNewPolicy(payload);
#     setIssuedPolicyId(res.data.policy_id);
#     setSuccessMessage(`Policy ${res.data.policy_id} issued! Valid until ${res.data.end_date}`);
#   };
#
# ── Renewal.jsx: call processRenewal on "Process Renewal" button click ────
#   const handleProcessRenewal = async () => {
#     const res = await insuranceAPI.processRenewal({
#       policy_id: policy.policy_id,
#       proposed_sum_insured: editedSI,
#       new_ncb: editedNCB,
#       renewal_premium: result.gross_premium,
#       net_premium: result.net_premium,
#       number_of_claims: policy.claims.total_claims,
#       total_claim_amount: policy.claims.total_amount,
#       highest_claim: policy.claims.highest_claim,
#       premium_change_pct: result.premium_change_pct,
#       renewal_status: result.recommendation,
#     });
#     showSuccessToast(`Policy renewed! Valid until ${res.data.end_date}`);
#   };
