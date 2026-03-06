"""
engine.py  —  backend/utils/engine.py
Motor Insurance Premium Engine v3.1
- Loads rates from actuarial_table.json (not hardcoded)
- Uses ML rate_model for premium (not hardcoded VEHICLE_BASE_RATES)
- Uses ML risk_model for risk scoring
- Blends actuarial + ML: 35% actuarial / 65% ML
- Full feature vector matches training pipeline exactly
"""

import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"


class MotorInsurancePremiumEngine:

    # Tax rates (fixed by IRCSL — only change by regulation)
    STAMP_DUTY = 0.010
    VAT        = 0.080
    CESS       = 0.005

    def __init__(self):
        self.risk_pipeline    = None
        self.rate_pipeline    = None   # NEW: ML rate model
        self.renew_pipeline   = None

        self.risk_features    = []
        self.rate_features    = []     # NEW: rate model features
        self.renew_features   = []
        self.risk_encoders    = {}
        self.premium_encoders = {}     # NEW: separate encoders for rate model

        self.expected_severity: float = 0.0   # populated by _load() from severity_model.json or DB
        self.optimal_threshold = 0.35      # cost-sensitive threshold

        # Actuarial table (loaded from JSON — not hardcoded)
        self.actuarial         = {}
        self.BASE_RATES        = {}
        self.AGE_LOADING       = {}
        self.MIN_PREMIUM       = 15_000
        self.BLEND_ACTUARIAL   = 0.35
        self.BLEND_ML          = 0.65

        # Governance metadata
        self.metadata          = {}
        # Dynamic severity (from DB-computed JSON — not hardcoded)
        self.severity_model    = {}
        self.base_frequency: float = 0.0   # populated by _load() from severity_model.json or DB
        # Real SHAP engine
        self.shap_engine       = None

        self._ready = False
        self._load()

    # ─────────────────────────────────────────────────────────────────────────
    # LOAD
    # ─────────────────────────────────────────────────────────────────────────

    def _load(self):
        """Load actuarial table, ML models, and governance metadata."""

        # 1. Actuarial table (rates from JSON — not hardcoded in source)
        act_path = MODEL_DIR / "actuarial_table.json"
        if act_path.exists():
            with open(act_path) as f:
                self.actuarial = json.load(f)
            self.BASE_RATES  = self.actuarial.get("base_rates", {})
            self.AGE_LOADING = {int(k): v for k, v in self.actuarial.get("vehicle_age_loading", {}).items()}
            self.MIN_PREMIUM = self.actuarial.get("min_premium_lkr", 15_000)
            blend = self.actuarial.get("blend_actuarial_ml", {})
            self.BLEND_ACTUARIAL = blend.get("actuarial_weight", 0.35)
            self.BLEND_ML        = blend.get("ml_weight", 0.65)
            print("Actuarial table loaded from actuarial_table.json")
        else:
            # Fallback if JSON missing — kept minimal
            self.BASE_RATES = {"Car": 0.030, "SUV": 0.035, "Van": 0.040, "Dual Purpose": 0.032}
            self.AGE_LOADING = {i: min(0.002 * i, 0.020) for i in range(10)}
            print("WARNING: actuarial_table.json not found — using fallback rates")

        # 2. Dynamic severity model from claims DB (not hardcoded)
        sev_path = MODEL_DIR / "severity_model.json"
        if sev_path.exists():
            with open(sev_path) as f:
                self.severity_model = json.load(f)
            ov = self.severity_model.get("overall", {})
            self.expected_severity = float(ov["avg_severity"])
            self.base_frequency    = float(ov["frequency"])
            print(f"Severity: freq={self.base_frequency:.4f} sev=Rs.{self.expected_severity:,.0f} "
                  f"pure_premium=Rs.{self.base_frequency*self.expected_severity:,.0f}")
        else:
            # JSON missing — compute from DB directly so value is never hardcoded
            self._compute_severity_from_db()

        # 3. Governance metadata
        meta_path = MODEL_DIR / "model_metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                self.metadata = json.load(f)
            print(f"Model metadata loaded: version {self.metadata.get('model_version','?')}")

        # 3. ML pipeline artifacts
        pipe_path = MODEL_DIR / "pipeline_artifacts.pkl"
        if pipe_path.exists():
            print("Loading ML pipeline artifacts…")
            with open(pipe_path, "rb") as f:
                arts = pickle.load(f)

            # ── Risk classifier ──────────────────────────────────────────
            self.risk_pipeline = (
                arts.get("risk_pipeline") or arts.get("risk_model")
                or arts.get("pipeline") or arts.get("clf")
            )
            self.risk_features = (
                arts.get("risk_features") or arts.get("features") or []
            )
            self.risk_encoders = (
                arts.get("encoders", {}).get("risk")
                or arts.get("encoders") or {}
            )

            # ── Rate model (ML premium prediction) ──────────────────────
            self.rate_pipeline = arts.get("rate_model")
            self.rate_features = arts.get("rate_features", [])
            self.premium_encoders = (
                arts.get("encoders", {}).get("premium")
                or self.risk_encoders   # fallback to risk encoders
            )

            # ── Renewal model ────────────────────────────────────────────
            self.renew_pipeline  = arts.get("renewal_model")
            self.renew_features  = arts.get("renewal_features", [])

            # 4. SHAP engine (real interventional SHAP, no external lib)
            if self.risk_pipeline is not None:
                try:
                    from backend.utils.shap_engine import SHAPEngine
                    self.shap_engine = SHAPEngine(self.risk_pipeline, self.risk_features)
                    print(f"SHAP engine ready (baseline={self.shap_engine.baseline_prob:.4f})")
                except Exception as e:
                    print(f"SHAP engine init error: {e}")

            self._ready = True
            print(f"ML models loaded: risk={self.risk_pipeline is not None}, "
                  f"rate={self.rate_pipeline is not None}, "
                  f"renewal={self.renew_pipeline is not None}")
            return

        # Legacy fallback
        rc_path = MODEL_DIR / "risk_classifier.pkl"
        if rc_path.exists():
            with open(rc_path, "rb") as f:
                rc = pickle.load(f)
            self.risk_pipeline = rc.get("model")
            self.risk_features = rc.get("features", [])
            self._ready = True
            print("Legacy risk model loaded")
            return

        print("No ML models found — rule-based engine only")
        self._ready = True

    # ─────────────────────────────────────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_severity_from_db(self):
        """
        Compute frequency and severity directly from the live claims and policies tables.
        Used as fallback when severity_model.json is unavailable.
        No constants — values are always derived from DB at runtime.
        """
        try:
            from backend.utils.database import get_connection
            with get_connection() as conn:
                row = conn.execute("""
                    SELECT
                        (SELECT COUNT(*) FROM claims WHERE claim_amount > 0) * 1.0
                            / NULLIF((SELECT COUNT(*) FROM policies), 0)  AS frequency,
                        (SELECT AVG(claim_amount)  FROM claims WHERE claim_amount > 0) AS avg_severity
                """).fetchone()
            freq, sev = row
            self.base_frequency    = float(freq or 0.0)
            self.expected_severity = float(sev  or 0.0)
            print(f"Severity from DB: freq={self.base_frequency:.6f} "
                  f"sev=Rs.{self.expected_severity:,.0f} "
                  f"pure_premium=Rs.{self.base_frequency*self.expected_severity:,.0f}")
        except Exception as exc:
            self.base_frequency    = 0.0
            self.expected_severity = 0.0
            print(f"WARNING: severity DB query failed — {exc}")

    def is_ready(self):
        return self._ready

    def model_info(self):
        """Return governance summary for API consumers."""
        return {
            "version":           self.metadata.get("model_version", "unknown"),
            "trained_at":        self.metadata.get("trained_at", "unknown"),
            "risk_auc":          self.metadata.get("risk_classifier", {}).get("auc_roc"),
            "rate_r2":           self.metadata.get("rate_model", {}).get("r2_score"),
            "actuarial_version": self.actuarial.get("_meta", {}).get("version", "unknown"),
            "blend":             f"{int(self.BLEND_ACTUARIAL*100)}% actuarial / {int(self.BLEND_ML*100)}% ML",
            "models_loaded": {
                "risk":    self.risk_pipeline is not None,
                "rate":    self.rate_pipeline is not None,
                "renewal": self.renew_pipeline is not None,
            }
        }

    # ─────────────────────────────────────────────────────────────────────────
    # ENCODING HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _encode(self, col: str, val: str, encoders: dict) -> int:
        """Label-encode a categorical value using stored encoder."""
        le = encoders.get(col) if isinstance(encoders, dict) else None
        if le is None:
            return 0
        try:
            return int(le.transform([str(val)])[0])
        except Exception:
            try:
                return int(le.transform([le.classes_[0]])[0])
            except Exception:
                return 0

    # ─────────────────────────────────────────────────────────────────────────
    # FEATURE BUILDERS — must match training pipeline exactly
    # ─────────────────────────────────────────────────────────────────────────

    def _risk_features_dict(self, p: dict) -> dict:
        """
        Build the exact 20-feature vector used to train the risk classifier.
        Feature names must match risk_features list from artifact.
        """
        age = float(p.get("driver_age", 35))
        exp = float(p.get("years_exp", 5))
        cc  = float(p.get("engine_cc", 1500))
        va  = float(p.get("vehicle_age", 5))
        ncb = float(p.get("prev_ncb", 0))

        enc = self.risk_encoders
        return {
            "Driver_Age":               age,
            "Years_Driving_Experience": exp,
            "Experience_Rate":          exp / max(1.0, age - 16.0),
            "Age_x_Exp":                age * exp,
            "Is_Young_Driver":          1 if age < 25 else 0,
            "Is_Senior_Driver":         1 if age > 65 else 0,
            "Is_New_Driver":            1 if exp < 2  else 0,
            "Is_Exp_Driver":            1 if exp > 15 else 0,
            "Engine_CC":                cc,
            "Vehicle_Age_Years":        va,
            "CC_x_VehicleAge":          cc * va,
            "High_CC":                  1 if cc > 2500 else 0,
            "Old_Vehicle":              1 if va > 10  else 0,
            "Previous_NCB_Percentage":  ncb,
            "High_NCB":                 1 if ncb >= 30 else 0,
            "Gender_enc":               self._encode("Gender",            p.get("gender", "Male"),        enc),
            "Vehicle_Type_enc":         self._encode("Vehicle_Type",      p.get("vehicle_type", "Car"),   enc),
            "Occupation_enc":           self._encode("Occupation",        p.get("occupation", "Other"),   enc),
            "Province_enc":             self._encode("Province",          p.get("province", "Western"),   enc),
            "Vehicle_Condition_enc":    self._encode("Vehicle_Condition", p.get("vehicle_condition", "Good"), enc),
        }

    def _rate_features_dict(self, p: dict, risk_score: int) -> dict:
        """
        Build the exact 16-feature vector used to train the rate model.
        Feature names must match rate_features list from artifact.
        Note: uses 'Years_of_Driving_Experience' (not 'Years_Driving_Experience').
        """
        age = float(p.get("driver_age", 35))
        exp = float(p.get("years_exp", 5))
        cc  = float(p.get("engine_cc", 1500))
        va  = float(p.get("vehicle_age", 5))
        si  = float(p.get("sum_insured", 1_000_000))
        mv  = float(p.get("market_value", si))
        ncb = float(p.get("prev_ncb", 0))
        bl  = 1 if str(p.get("is_blacklisted", "No")).lower() in ("yes", "true", "1") else 0
        reb = 1 if str(p.get("rebate_approved", "No")).lower() in ("yes", "true", "1") else 0
        ex  = 1 if str(p.get("is_existing_customer", "No")).lower() in ("yes", "true", "1") else 0

        enc = self.premium_encoders
        return {
            "Driver_Age":                   age,
            "Years_of_Driving_Experience":  exp,          # note: different name from risk features
            "Experience_Rate":              exp / max(1.0, age - 16.0),
            "Is_Young_Driver":              1 if age < 25 else 0,
            "Is_Senior_Driver":             1 if age > 65 else 0,
            "Engine_CC":                    cc,
            "Vehicle_Age_Years":            va,
            "Vehicle_Type_enc":             self._encode("Vehicle_Type", p.get("vehicle_type", "Car"),   enc),
            "Province_enc":                 self._encode("Province",     p.get("province", "Western"),   enc),
            "Occupation_enc":               self._encode("Occupation",   p.get("occupation", "Other"),   enc),
            "NCB_Claimed_Percentage":       ncb,
            "Is_Blacklisted":               bl,
            "Is_Existing_Customer":         ex,
            "Risk_Score":                   risk_score,
            "SI_MV_Ratio":                  si / max(1.0, mv),
            "Rebate_Approved":              reb,
        }

    def _build_row(self, feature_dict: dict, feature_list: list) -> np.ndarray:
        """
        Convert feature dict to numpy array in exact training column order.
        Returns numpy array (not DataFrame) to match how the model was trained
        (HistGBM was fitted without feature names — using array avoids warnings).
        """
        return np.array([[feature_dict.get(f, 0.0) for f in feature_list]])

    # ─────────────────────────────────────────────────────────────────────────
    # ACTUARIAL PREMIUM (from JSON table — no hardcoded numbers in code)
    # ─────────────────────────────────────────────────────────────────────────

    def _actuarial_rate(self, p: dict) -> float:
        """
        Compute base rate from actuarial_table.json.
        Rate = base_rate[vehicle_type]
             + vehicle_age_loading[va]
             + driver_age_loading
             + experience_discount
             + province_loading
             + vehicle_condition_loading
             + engine_cc_loading
        """
        vt   = str(p.get("vehicle_type", "Car"))
        va   = int(p.get("vehicle_age", 0))
        age  = int(p.get("driver_age", 35))
        exp  = int(p.get("years_exp", 5))
        prov = str(p.get("province", "Western"))
        cond = str(p.get("vehicle_condition", "Good"))
        cc   = int(p.get("engine_cc", 1500))
        bl   = str(p.get("is_blacklisted", "No")).lower() in ("yes", "true", "1")

        rate = self.BASE_RATES.get(vt, 0.030)
        rate += self.AGE_LOADING.get(min(va, 9), 0.020)

        # Driver age loading
        da = self.actuarial.get("driver_age_loading", {})
        if   age <= 25: rate += da.get("16_25", 0.018)
        elif age <= 35: rate += da.get("26_35", 0.000)
        elif age <= 50: rate += da.get("36_50", -0.002)
        elif age <= 65: rate += da.get("51_65", 0.003)
        else:           rate += da.get("66_plus", 0.010)

        # Experience discount
        ed = self.actuarial.get("experience_discount", {})
        if   exp <= 2:  rate += ed.get("0_2_years",  0.012)
        elif exp <= 5:  rate += ed.get("3_5_years",  0.000)
        elif exp <= 10: rate += ed.get("6_10_years", -0.003)
        else:           rate += ed.get("11_plus",    -0.006)

        # Province loading
        pl = self.actuarial.get("province_loading", {})
        rate += pl.get(prov, 0.0)

        # Vehicle condition
        cl = self.actuarial.get("vehicle_condition_loading", {})
        rate += cl.get(cond, 0.0)

        # Engine CC loading
        el = self.actuarial.get("engine_cc_loading", {})
        if   cc <= 1000: rate += el.get("0_1000",   -0.004)
        elif cc <= 1500: rate += el.get("1001_1500",  0.000)
        elif cc <= 2000: rate += el.get("1501_2000",  0.004)
        elif cc <= 2500: rate += el.get("2001_2500",  0.007)
        else:            rate += el.get("2501_plus",  0.012)

        # Blacklist surcharge
        if bl:
            rate += self.actuarial.get("blacklist_surcharge", 0.50)

        return max(0.020, min(0.080, rate))

    def calc_rule_based_premium(self, p: dict) -> dict:
        """Full actuarial premium from the JSON rate table."""
        si  = float(p.get("sum_insured", 1_000_000))
        ncb = float(p.get("prev_ncb", 0))

        rate = self._actuarial_rate(p)
        net  = si * rate
        if ncb > 0:
            net *= (1 - ncb / 100)
        net = max(self.MIN_PREMIUM, net)

        stamp = int(net * self.STAMP_DUTY)
        vat   = int(net * self.VAT)
        cess  = int(net * self.CESS)

        return {
            "net_premium":  int(net),
            "stamp_duty":   stamp,
            "vat":          vat,
            "cess":         cess,
            "gross_premium": int(net) + stamp + vat + cess,
            "rate_applied": round(rate, 5),
            "doc_complete": True,
        }

    # Backward compat alias used by renewal.py
    def _row(self, proposal: dict, feats: list) -> pd.DataFrame:
        d = self._risk_features_dict(proposal)
        return self._build_row(d, feats)

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN CALCULATION
    # ─────────────────────────────────────────────────────────────────────────

    def calculate(self, proposal: dict) -> dict:
        """
        Full premium + risk calculation.
        Step 1: ML risk score (CalibratedClassifierCV on 20 features)
        Step 2: ML rate prediction (GBR on 16 features, predicts rate_pct)
        Step 3: Actuarial rate (from actuarial_table.json)
        Step 4: Blend — 35% actuarial / 65% ML
        Step 5: Apply NCB, taxes, floor
        """
        if not self._ready:
            raise RuntimeError("Engine not ready")

        si  = float(proposal.get("sum_insured", 1_000_000))
        ncb = float(proposal.get("prev_ncb", 0))

        # ── Step 1: Risk score ───────────────────────────────────────────
        if self.risk_pipeline is not None and self.risk_features:
            X_risk   = self._build_row(self._risk_features_dict(proposal), self.risk_features)
            acc_prob = float(self.risk_pipeline.predict_proba(X_risk)[0, 1])
        else:
            acc_prob = 0.25   # fallback if risk model not loaded

        risk_score = min(100, max(0, int(acc_prob * 100)))
        risk_label = (
            "HIGH"   if acc_prob >= 0.5
            else "MEDIUM" if acc_prob >= self.optimal_threshold
            else "LOW"
        )

        # ── Step 2: ML rate prediction ───────────────────────────────────
        if self.rate_pipeline is not None and self.rate_features:
            X_rate   = self._build_row(self._rate_features_dict(proposal, risk_score), self.rate_features)
            ml_rate  = float(self.rate_pipeline.predict(X_rate)[0])
            ml_rate  = max(0.020, min(0.080, ml_rate))   # sanity clamp
        else:
            ml_rate  = None

        # ── Step 3: Actuarial rate ────────────────────────────────────────
        act_rate = self._actuarial_rate(proposal)

        # ── Step 4: Blend ─────────────────────────────────────────────────
        if ml_rate is not None:
            blended_rate = self.BLEND_ACTUARIAL * act_rate + self.BLEND_ML * ml_rate
        else:
            blended_rate = act_rate   # no ML → pure actuarial

        # ── Step 5: Apply NCB and compute net premium ─────────────────────
        base  = si * blended_rate
        if ncb > 0:
            base *= (1 - ncb / 100)
        net   = max(self.MIN_PREMIUM, base)
        net   = int(net)

        # Compute base_premium (before NCB) for display
        denom        = (1 - ncb / 100) if ncb < 100 else 1.0
        base_premium = int(net / denom) if denom > 0 else net
        ncb_discount = base_premium - net

        stamp = int(net * self.STAMP_DUTY)
        vat   = int(net * self.VAT)
        cess  = int(net * self.CESS)
        gross = net + stamp + vat + cess

        return {
            "risk_score":               risk_score,
            "accident_probability_pct": round(acc_prob * 100, 2),
            "risk_label":               risk_label,
            "base_premium":             base_premium,
            "ncb_discount":             ncb_discount,
            "net_premium":              net,
            "stamp_duty":               stamp,
            "vat":                      vat,
            "cess":                     cess,
            "gross_premium":            gross,
            "doc_complete":             True,
            "rate_debug": {
                "actuarial_rate_pct": round(act_rate * 100, 3),
                "ml_rate_pct":        round((ml_rate or 0) * 100, 3),
                "blended_rate_pct":   round(blended_rate * 100, 3),
                "blend":              f"{int(self.BLEND_ACTUARIAL*100)}% actuarial + {int(self.BLEND_ML*100)}% ML",
            },
            "breakdown": {
                "net":   net,
                "stamp": stamp,
                "vat":   vat,
                "cess":  cess,
                "gross": gross,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # RENEWAL PREMIUM — uses the ML renewal model
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_renewal_premium(self, renewal_input: dict) -> Optional[float]:
        """
        Use the trained renewal_model (HistGBR) to predict renewal premium.
        Falls back to None if model not available — caller uses rule-based logic.

        renewal_input keys:
          previous_premium, previous_ncb, new_ncb,
          number_of_claims, total_claim_amount, highest_claim,
          days_since_last_claim, vehicle_age, driver_age,
          years_with_company, si_mv_ratio, claim_pattern
        """
        if self.renew_pipeline is None or not self.renew_features:
            return None

        enc = self.premium_encoders
        cfp_le = enc.get("Claim_Frequency_Pattern") if isinstance(enc, dict) else None

        def encode_cfp(val: str) -> int:
            if cfp_le is None:
                return 0
            try:
                return int(cfp_le.transform([val])[0])
            except Exception:
                return 0

        # Map claim pattern
        n_claims = int(renewal_input.get("number_of_claims", 0))
        if   n_claims == 0: cfp = "No Claims"
        elif n_claims == 1: cfp = "Single Claim"
        else:               cfp = "Multiple Claims"

        row = {
            "Previous_Premium_LKR":             float(renewal_input.get("previous_premium", 0)),
            "Previous_NCB_Percentage":          float(renewal_input.get("previous_ncb", 0)),
            "New_NCB_Percentage":               float(renewal_input.get("new_ncb", 0)),
            "Number_of_Claims":                 n_claims,
            "Total_Claim_Amount_Last_Year_LKR": float(renewal_input.get("total_claim_amount", 0)),
            "Highest_Claim_Amount_LKR":         float(renewal_input.get("highest_claim", 0)),
            "Days_Since_Last_Claim":            float(renewal_input.get("days_since_last_claim", 999)),
            "Vehicle_Current_Age":              float(renewal_input.get("vehicle_age", 5)),
            "Driver_Age":                       float(renewal_input.get("driver_age", 35)),
            "Years_With_Company":               float(renewal_input.get("years_with_company", 1)),
            "Sum_Insured_Inline_Market":        float(renewal_input.get("si_mv_ratio", 0.95)),
            "Claim_Frequency_Pattern_enc":      encode_cfp(cfp),
        }

        X = pd.DataFrame([[row.get(f, 0.0) for f in self.renew_features]],
                         columns=self.renew_features)
        try:
            predicted = float(self.renew_pipeline.predict(X)[0])
            return max(self.MIN_PREMIUM, predicted)
        except Exception as e:
            print(f"Renewal model prediction error: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_engine: Optional[MotorInsurancePremiumEngine] = None


def get_engine() -> MotorInsurancePremiumEngine:
    global _engine
    if _engine is None:
        _engine = MotorInsurancePremiumEngine()
    return _engine
