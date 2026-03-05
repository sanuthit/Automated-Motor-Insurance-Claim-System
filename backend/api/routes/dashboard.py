from fastapi import APIRouter
from ...utils.database import get_connection

router = APIRouter()

@router.get("/dashboard/stats")
async def dashboard_stats():
    try:
        with get_connection() as conn:
            # KPIs
            total_policies = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
            avg_premium    = conn.execute("SELECT AVG(calculated_premium) FROM policies WHERE calculated_premium > 0").fetchone()[0]
            avg_claim      = conn.execute("SELECT AVG(claim_amount) FROM claims").fetchone()[0]
            total_claims   = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
            approved       = conn.execute("SELECT COUNT(*) FROM claims WHERE LOWER(claim_status) LIKE '%approv%'").fetchone()[0]
            ncb_eligible   = conn.execute("SELECT COUNT(*) FROM policies WHERE ncb_pct > 0").fetchone()[0]
            high_risk      = conn.execute("SELECT COUNT(*) FROM policies WHERE risk_score >= 70").fetchone()[0]
            male_ct        = conn.execute("SELECT COUNT(*) FROM policies WHERE gender='Male'").fetchone()[0]
            female_ct      = conn.execute("SELECT COUNT(*) FROM policies WHERE gender='Female'").fetchone()[0]

            # Age → risk
            age_rows = conn.execute("""
                SELECT
                    CASE
                        WHEN driver_age BETWEEN 16 AND 25 THEN '16-25'
                        WHEN driver_age BETWEEN 26 AND 35 THEN '26-35'
                        WHEN driver_age BETWEEN 36 AND 45 THEN '36-45'
                        WHEN driver_age BETWEEN 46 AND 55 THEN '46-55'
                        WHEN driver_age BETWEEN 56 AND 65 THEN '56-65'
                        ELSE '65+'
                    END AS age_group,
                    AVG(risk_score) AS avg_risk,
                    COUNT(*) AS policy_count
                FROM policies
                GROUP BY age_group
                ORDER BY MIN(driver_age)
            """).fetchall()

            # Province risk
            prov_rows = conn.execute("""
                SELECT p.province,
                       AVG(p.risk_score)       AS avg_risk,
                       COUNT(DISTINCT p.policy_id) AS policy_count,
                       COUNT(c.claim_id)        AS claim_count
                FROM policies p
                LEFT JOIN claims c ON p.policy_id = c.policy_number
                GROUP BY p.province
                ORDER BY avg_risk DESC
            """).fetchall()

            # Claim types
            claim_rows = conn.execute("""
                SELECT claim_type, COUNT(*) AS cnt, AVG(claim_amount) AS avg_amt
                FROM claims
                GROUP BY claim_type
                ORDER BY cnt DESC
                LIMIT 10
            """).fetchall()

            # Vehicle types
            veh_rows = conn.execute("""
                SELECT vehicle_type, COUNT(*) AS cnt
                FROM policies
                WHERE vehicle_type NOT IN ('Motor Cycle','')
                GROUP BY vehicle_type
                ORDER BY cnt DESC
            """).fetchall()

            # Risk distribution buckets
            rd = conn.execute("""
                SELECT
                    SUM(CASE WHEN risk_score < 40  THEN 1 ELSE 0 END) AS low,
                    SUM(CASE WHEN risk_score >= 40 AND risk_score < 70 THEN 1 ELSE 0 END) AS medium,
                    SUM(CASE WHEN risk_score >= 70 THEN 1 ELSE 0 END) AS high
                FROM policies
            """).fetchone()

            # NCB distribution
            ncb_rows = conn.execute("""
                SELECT ncb_pct, COUNT(*) AS cnt
                FROM policies
                GROUP BY ncb_pct
                ORDER BY ncb_pct
            """).fetchall()

            # Occupation distribution (top 8)
            occ_rows = conn.execute("""
                SELECT occupation, COUNT(*) AS cnt, AVG(risk_score) AS avg_risk
                FROM policies
                GROUP BY occupation
                ORDER BY cnt DESC
                LIMIT 8
            """).fetchall()

            # Engine CC buckets
            cc_rows = conn.execute("""
                SELECT
                    CASE
                        WHEN engine_cc < 1000 THEN '<1000cc'
                        WHEN engine_cc < 1500 THEN '1000–1500cc'
                        WHEN engine_cc < 2000 THEN '1500–2000cc'
                        WHEN engine_cc < 3000 THEN '2000–3000cc'
                        ELSE '3000cc+'
                    END AS bucket,
                    COUNT(*) AS cnt,
                    AVG(risk_score) AS avg_risk
                FROM policies
                GROUP BY bucket
                ORDER BY MIN(engine_cc)
            """).fetchall()

            # Feature importance from ML model
            try:
                import pickle, os
                MODEL_PATH = os.path.join(os.path.dirname(__file__), '../../models/pipeline_artifacts.pkl')
                with open(MODEL_PATH, 'rb') as f:
                    arts = pickle.load(f)
                model = arts.get('risk_model')
                features = arts.get('risk_features', [])
                feat_imp = []
                if model and hasattr(model, 'estimator') and hasattr(model.estimator, 'feature_importances_'):
                    imps = model.estimator.feature_importances_
                    feat_imp = sorted(
                        [{"feature": f, "importance": round(float(v), 4)} for f, v in zip(features, imps)],
                        key=lambda x: -x["importance"]
                    )[:10]
            except Exception:
                feat_imp = []

        return {
            "total_policies":      total_policies,
            "avg_premium":         round(avg_premium or 0, 2),
            "avg_claim_amount":    round(avg_claim or 0, 2),
            "total_claims":        total_claims,
            "claim_approval_rate": round((approved / total_claims * 100) if total_claims else 0, 1),
            "ncb_rate":            round((ncb_eligible / total_policies * 100) if total_policies else 0, 1),
            "accident_rate":       round((high_risk / total_policies * 100) if total_policies else 0, 1),
            "gender_male":         male_ct,
            "gender_female":       female_ct,
            "model_auc":           0.731,
            "model_r2":            0.641,
            "risk_distribution": [
                {"category": "Low Risk (<40)",    "count": rd[0] or 0},
                {"category": "Medium Risk (40-70)","count": rd[1] or 0},
                {"category": "High Risk (70+)",   "count": rd[2] or 0},
            ],
            "age_risk": [
                {"age_group": r[0], "avg_risk": round(r[1] or 0, 1), "policy_count": r[2]}
                for r in age_rows
            ],
            "province_risk": [
                {"province": r[0], "avg_risk": round(r[1] or 0, 1),
                 "policy_count": r[2], "claim_count": r[3]}
                for r in prov_rows
            ],
            "claim_types": [
                {"type": r[0], "count": r[1], "avg_amount": round(r[2] or 0, 0)}
                for r in claim_rows
            ],
            "vehicle_types": [
                {"name": r[0], "value": r[1]}
                for r in veh_rows
            ],
            "ncb_distribution": [
                {"ncb": int(r[0]), "count": r[1]}
                for r in ncb_rows
            ],
            "occupation_risk": [
                {"occupation": r[0], "count": r[1], "avg_risk": round(r[2] or 0, 1)}
                for r in occ_rows
            ],
            "engine_cc_risk": [
                {"bucket": r[0], "count": r[1], "avg_risk": round(r[2] or 0, 1)}
                for r in cc_rows
            ],
            "feature_importance": feat_imp,
        }
    except Exception as e:
        return {"error": str(e)}
