
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Any, Dict, List

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"


class MotorInsurancePremiumEngine:
    # ── Sri Lanka 2024 statutory levies ─────────────────────────────────
    STAMP_DUTY = 0.010  # 1.0%
    VAT = 0.080         # 8.0%
    CESS = 0.005        # 0.5%

    # ── Market norm base rates ───────────────────────────────────────────
    VEHICLE_BASE_RATES = {
        "Car": 0.030,
        "SUV": 0.035,
        "Van": 0.040,
        "Dual Purpose": 0.032,
    }

    # Age-loading added to base rate (per year of vehicle age, capped)
    AGE_LOADING = {
        0: 0.000, 1: 0.002, 2: 0.003, 3: 0.005, 4: 0.007,
        5: 0.010, 6: 0.012, 7: 0.015, 8: 0.018, 9: 0.020,
    }

    MIN_PREMIUM = 15_000
    MAX_SI_RATIO = 1.10
    MIN_SI_RATIO = 0.90

    # ── Used in actuarial add-on endpoint (you already expose) ───────────
    EXPENSE_RATIO = 0.30
    PROFIT_MARGIN = 0.05

    # If you referenced MIN_RATE_PCT in routes, define it safely:
    MIN_RATE_PCT = 0.020  # fallback minimum rating floor (2%) for actuarial endpoint

    # ── fallback categorical maps (ONLY used if encoder missing) ─────────
    _PROVINCE_MAP = {
        "Central": 0, "Eastern": 1, "North Central": 2, "North Western": 3,
        "Northern": 4, "Sabaragamuwa": 5, "Southern": 6, "Uva": 7, "Western": 8
    }
    _OCCUPATION_MAP = {
        "Accountant": 0, "Business Owner": 1, "Doctor": 2, "Driver": 3,
        "Engineer": 4, "Government Employee": 5, "Lawyer": 6, "Other": 7,
        "Private Sector Employee": 8, "Professional": 9, "Retired": 10,
        "Self Employed": 11, "Student": 12, "Teacher": 13,
        # your UI values:
        "Employed": 8, "Self-Employed": 11, "Government": 5,
        "Unemployed": 7, "Driver/Transport": 3,
    }
    _VT_MAP = {"Car": 0, "Dual Purpose": 1, "SUV": 2, "Van": 3}
    _GENDER_MAP = {"Female": 0, "Male": 1}
    _COND_MAP = {"Poor": 0, "Fair": 1, "Good": 2, "Excellent": 3}

    def __init__(self):
        self.risk_pipeline = None
        self.prem_pipeline = None
        self.renew_pipeline = None

        self.risk_features: List[str] = []
        self.prem_features: List[str] = []
        self.renew_features: List[str] = []

        self.expected_severity = 725_796
        self.optimal_threshold = 0.35

        # Encoders (optional)
        self._province_enc = None
        self._occupation_enc = None
        self._vt_enc = None
        self._gender_enc = None
        self._cond_enc = None

        # SHAP package (optional)
        self.shap_pkg = None

        self._ready = False
        self._load()

    # ----------------------------------------------------
    # LOAD ML MODELS + SHAP
    # ----------------------------------------------------
    def _load(self):
        pipe_path = MODEL_DIR / "pipeline_artifacts.pkl"

        if pipe_path.exists():
            print(f"Loading pipeline artifacts: {pipe_path}")
            with open(pipe_path, "rb") as f:
                arts = pickle.load(f)

            # risk
            risk_block = arts.get("risk") or arts.get("risk_model") or arts.get("risk_pipeline")
            if isinstance(risk_block, dict):
                self.risk_pipeline = risk_block.get("pipeline") or risk_block.get("model") or risk_block.get("clf")
                self.risk_features = risk_block.get("features") or risk_block.get("feature_list") or []
            else:
                self.risk_pipeline = arts.get("risk_pipeline") or arts.get("pipeline") or arts.get("model") or arts.get("clf")
                self.risk_features = arts.get("risk_features") or arts.get("features") or arts.get("feature_list") or []

            # premium (optional)
            prem_block = arts.get("premium")
            if isinstance(prem_block, dict):
                self.prem_pipeline = prem_block.get("pipeline") or prem_block.get("model")
                self.prem_features = prem_block.get("features") or prem_block.get("feature_list") or []

            # renewal (optional)
            renew_block = arts.get("renewal")
            if isinstance(renew_block, dict):
                self.renew_pipeline = renew_block.get("pipeline") or renew_block.get("model")
                self.renew_features = renew_block.get("features") or renew_block.get("feature_list") or []

            # encoders (optional)
            enc = arts.get("encoders", {}) if isinstance(arts, dict) else {}
            if isinstance(enc, dict):
                self._province_enc = enc.get("Province")
                self._occupation_enc = enc.get("Occupation")
                self._vt_enc = enc.get("Vehicle_Type")
                self._gender_enc = enc.get("Gender")
                self._cond_enc = enc.get("Vehicle_Condition")

            # load shap pkg if exists
            shap_path = MODEL_DIR / "shap_explainer.pkl"
            if shap_path.exists():
                try:
                    with open(shap_path, "rb") as f:
                        self.shap_pkg = pickle.load(f)
                    # allow threshold to be stored in shap pkg
                    if isinstance(self.shap_pkg, dict):
                        self.optimal_threshold = float(self.shap_pkg.get("optimal_threshold", self.optimal_threshold))
                    print(f"SHAP explainer loaded: {shap_path}")
                except Exception as ex:
                    print(f"WARNING: Failed to load shap_explainer.pkl: {ex}")
                    self.shap_pkg = None

            self._ready = True
            print("Model artifacts loaded successfully")
            if self.risk_pipeline is None:
                print("WARNING: risk_pipeline not found in artifacts")
            return

        # legacy fallback
        rc_path = MODEL_DIR / "risk_classifier.pkl"
        rm_path = MODEL_DIR / "regression_models.pkl"

        if rc_path.exists() and rm_path.exists():
            print("Loading legacy models...")
            with open(rc_path, "rb") as f:
                rc = pickle.load(f)
            with open(rm_path, "rb") as f:
                rm = pickle.load(f)

            self.risk_pipeline = rc.get("model")
            self.risk_features = rc.get("features", rc.get("original_features", [])) or []

            prem = rm.get("premium", {})
            if isinstance(prem, dict):
                self.prem_pipeline = prem.get("model")
                self.prem_features = prem.get("features", []) or []

            self.optimal_threshold = float(rc.get("optimal_threshold", self.optimal_threshold))

            # expected severity if exists
            fs_path = MODEL_DIR / "freq_sev_model.pkl"
            if fs_path.exists():
                try:
                    with open(fs_path, "rb") as f:
                        fs = pickle.load(f)
                    self.expected_severity = float(fs.get("expected_severity", self.expected_severity))
                except Exception:
                    pass

            # shap
            shap_path = MODEL_DIR / "shap_explainer.pkl"
            if shap_path.exists():
                try:
                    with open(shap_path, "rb") as f:
                        self.shap_pkg = pickle.load(f)
                    if isinstance(self.shap_pkg, dict):
                        self.optimal_threshold = float(self.shap_pkg.get("optimal_threshold", self.optimal_threshold))
                    print(f"SHAP explainer loaded: {shap_path}")
                except Exception as ex:
                    print(f"WARNING: Failed to load shap_explainer.pkl: {ex}")
                    self.shap_pkg = None

            self._ready = True
            print("Legacy models loaded")
            return

        print(f"No ML models found in {MODEL_DIR}. System will run rule-based premium only.")
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    # ----------------------------------------------------
    # RULE-BASED PREMIUM ENGINE (REALISTIC)
    # ----------------------------------------------------
    def calc_rule_based_premium(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        mv = float(proposal.get("market_value", proposal.get("sum_insured", 1_000_000)))
        si = float(proposal.get("sum_insured", mv))
        vt = str(proposal.get("vehicle_type", "Car"))
        va = int(proposal.get("vehicle_age", 0))
        ncb = float(proposal.get("prev_ncb", 0))
        bl = str(proposal.get("is_blacklisted", "No")).strip().lower() in ("yes", "true", "1")

        # Validate SI range (90%–110% of MV)
        si_validated = max(si, mv * self.MIN_SI_RATIO)
        si_validated = min(si_validated, mv * self.MAX_SI_RATIO)

        si_warning = None
        if si < mv * self.MIN_SI_RATIO:
            si_warning = f"SI adjusted from Rs.{si:,.0f} to minimum Rs.{si_validated:,.0f} (90% of MV)"
        elif si > mv * self.MAX_SI_RATIO:
            si_warning = f"SI adjusted from Rs.{si:,.0f} to maximum Rs.{si_validated:,.0f} (110% of MV)"

        base_rate = self.VEHICLE_BASE_RATES.get(vt, self.VEHICLE_BASE_RATES["Car"])
        age_load = self.AGE_LOADING.get(min(va, 9), 0.020)
        total_rate = base_rate + age_load

        net = si_validated * total_rate
        adjustments = [f"Base rate {base_rate*100:.1f}% ({vt})"]
        if age_load > 0:
            adjustments.append(f"Age loading +{age_load*100:.1f}% (vehicle {va}yr)")

        # NCB discount
        ncb_amount = 0
        if ncb > 0:
            ncb_amount = int(net * (ncb / 100))
            net -= ncb_amount
            adjustments.append(f"NCB {ncb:.0f}% discount: -Rs.{ncb_amount:,}")

        # blacklist surcharge
        if bl:
            net = net * 1.50
            adjustments.append("Blacklist surcharge +50%")

        # documents
        doc_keys = ["images", "inspection", "reg_book", "fair_value"]
        doc_ok = all(str(proposal.get(k, "Yes")).strip().lower() in ("yes", "true", "1") for k in doc_keys)

        if doc_ok and str(proposal.get("rebate_approved", "No")).strip().lower() in ("yes", "true", "1"):
            net = net * 0.97
            adjustments.append("Document rebate -3%")

        net = max(self.MIN_PREMIUM, net)

        stamp = int(net * self.STAMP_DUTY)
        vat = int(net * self.VAT)
        cess = int(net * self.CESS)
        gross = int(net) + stamp + vat + cess

        return {
            "net_premium": int(net),
            "stamp_duty": stamp,
            "vat": vat,
            "cess": cess,
            "gross_premium": gross,
            "rate_applied": f"{total_rate*100:.2f}%",
            "si_used": int(si_validated),
            "si_warning": si_warning,
            "adjustments": adjustments,
            "doc_complete": doc_ok,
            "base_premium": int(si_validated * total_rate),
            "ncb_discount": int(ncb_amount),
        }

    # ----------------------------------------------------
    # ENCODING HELPERS (optional)
    # ----------------------------------------------------
    def _encode(self, name: str, raw_value: Any, fallback_map: Dict[str, int]) -> int:
        enc = None
        if name == "province":
            enc = self._province_enc
        elif name == "occupation":
            enc = self._occupation_enc
        elif name == "vehicle_type":
            enc = self._vt_enc
        elif name == "gender":
            enc = self._gender_enc
        elif name == "condition":
            enc = self._cond_enc

        if enc is not None:
            try:
                return int(enc.transform([str(raw_value)])[0])
            except Exception:
                pass

        return fallback_map.get(str(raw_value), list(fallback_map.values())[-1])

    # ----------------------------------------------------
    # FEATURE BUILDING (keep stable)
    # ----------------------------------------------------
    def _raw_dict(self, p: Dict[str, Any]) -> Dict[str, Any]:
        age = float(p.get("driver_age", 35))
        exp = float(p.get("years_exp", 10))
        cc = float(p.get("engine_cc", 1500))
        va = float(p.get("vehicle_age", 3))
        si = float(p.get("sum_insured", 5_000_000))
        mv = float(p.get("market_value", si))
        ncb = float(p.get("prev_ncb", 0))

        # robust categorical encodings
        gl = self._encode("gender", p.get("gender", "Male"), self._GENDER_MAP)
        ol = self._encode("occupation", p.get("occupation", "Private Sector Employee"), self._OCCUPATION_MAP)
        pl = self._encode("province", p.get("province", "Western"), self._PROVINCE_MAP)
        vl = self._encode("vehicle_type", p.get("vehicle_type", "Car"), self._VT_MAP)
        cl = self._encode("condition", p.get("vehicle_condition", "Good"), self._COND_MAP)

        # derived
        exp_rate = exp / max(1.0, age - 17.0)
        si_mv_ratio = si / max(1.0, mv)

        def _yn(k: str, d="No") -> int:
            v = p.get(k, d)
            if isinstance(v, bool):
                return int(v)
            return int(str(v).strip().lower() in ("yes", "true", "1"))

        return {
            # common / training style names
            "Driver_Age": age,
            "Years_Driving_Experience": exp,
            "Years_of_Driving_Experience": exp,
            "Engine_CC": cc,
            "Vehicle_Age_Years": va,
            "Sum_Insured_LKR": si,
            "Proposed_Sum_Insured_LKR": si,
            "Market_Value_LKR": mv,
            "Previous_NCB_Percentage": ncb,
            "NCB_Claimed_Percentage": ncb,

            # engineered
            "Experience_Rate": exp_rate,
            "Exp_Rate": exp_rate,
            "Age_x_Exp": age * exp,
            "Log_SI": np.log1p(si),
            "Log_MV": np.log1p(mv),
            "SI_MV_Ratio": si_mv_ratio,
            "CC_x_VehicleAge": cc * va,
            "High_NCB": int(ncb >= 40),

            "Is_Young": int(age < 26),
            "Is_Young_Driver": int(age < 26),
            "Is_Senior": int(age > 65),
            "Is_Senior_Driver": int(age > 65),
            "Is_New": int(exp < 3),
            "Is_New_Driver": int(exp < 3),

            # categorical encodings
            "Gender_le": gl, "Gender_enc": gl, "Gender_cat": gl,
            "Occupation_le": ol, "Occupation_enc": ol, "Occupation_cat": ol,
            "Province_le": pl, "Province_enc": pl, "Province_cat": pl,
            "Vehicle_Type_le": vl, "Vehicle_Type_enc": vl, "Vehicle_Type_cat": vl,
            "Vehicle_Condition_ord": cl,

            # binary flags
            "Is_Existing_Customer": _yn("is_existing_customer"),
            "Is_Blacklisted": _yn("is_blacklisted"),
            "Images_Uploaded": _yn("images", "Yes"),
            "Inspection_Report_Uploaded": _yn("inspection", "Yes"),
            "Fair_Value_Proposed": _yn("fair_value", "Yes"),
            "Financial_Interest_Recorded": _yn("financial_interest", "No"),
            "Registration_Book_Available": _yn("reg_book", "Yes"),
            "Rebate_Approved": _yn("rebate_approved", "No"),
            "Valid_Renewal_Notice": _yn("valid_renewal_notice", "No"),
        }

    def _row(self, proposal: Dict[str, Any], feats: List[str]) -> pd.DataFrame:
        d = self._raw_dict(proposal)
        return pd.DataFrame([[d.get(f, 0.0) for f in feats]], columns=feats)

    # ----------------------------------------------------
    # SHAP EXPLANATION (used by YOUR /explain endpoint)
    # ----------------------------------------------------
    def explain(self, proposal: Dict[str, Any], top_n: int = 5) -> Dict[str, Any]:
        """
        Returns SHAP drivers if shap_explainer.pkl is available.
        Falls back gracefully if not.
        """
        if not self.shap_pkg:
            return {"available": False, "message": "shap_explainer.pkl not found. Run your SHAP notebook to generate it."}

        try:
            explainer = self.shap_pkg.get("explainer") if isinstance(self.shap_pkg, dict) else None
            feat_names = []
            if isinstance(self.shap_pkg, dict):
                feat_names = self.shap_pkg.get("feature_names") or self.shap_pkg.get("features") or []
            if not feat_names:
                feat_names = self.risk_features

            if explainer is None or not feat_names:
                # fallback to global importance if stored
                fi = self.shap_pkg.get("shap_feature_importance", {}) if isinstance(self.shap_pkg, dict) else {}
                if not fi:
                    return {"available": False, "message": "SHAP explainer/feature list missing in shap_explainer.pkl"}
                top = sorted(fi.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]
                return {
                    "available": True,
                    "method": "global_SHAP",
                    "top_drivers": [self._format_driver(k, float(v), proposal) for k, v in top],
                }

            # local shap
            X = self._row(proposal, feat_names)
            sv = explainer.shap_values(X)

            # handle binary classifier list output
            if isinstance(sv, list):
                sv = sv[1] if len(sv) > 1 else sv[0]

            sv = np.array(sv).reshape(-1)  # (n_features,)
            pairs = sorted(zip(feat_names, sv), key=lambda x: abs(x[1]), reverse=True)[:top_n]

            return {
                "available": True,
                "method": "local_SHAP",
                "top_drivers": [self._format_driver(f, float(v), proposal) for f, v in pairs],
            }

        except Exception as ex:
            return {"available": False, "message": f"SHAP error: {ex}"}

    def _format_driver(self, feature: str, shap_val: float, proposal: Dict[str, Any]) -> Dict[str, Any]:
        direction = "increases_risk" if shap_val > 0 else "reduces_risk"
        mag = "high" if abs(shap_val) > 0.05 else "medium" if abs(shap_val) > 0.02 else "low"
        return {
            "feature": feature,
            "shap_value": round(float(shap_val), 4),
            "direction": direction,
            "magnitude": mag,
            "reason": self._human_reason(feature, shap_val, proposal),
        }

    def _human_reason(self, feature: str, shap_val: float, proposal: Dict[str, Any]) -> str:
        direction = "increases" if shap_val > 0 else "reduces"
        f = feature.lower()

        if ("driver_age" in f or f == "age") and "vehicle" not in f:
            age = int(float(proposal.get("driver_age", 35)))
            label = "young driver" if age < 26 else "senior driver" if age > 65 else f"age {age}"
            return f"Driver age {age} ({label}) {direction} risk"

        if "vehicle_age" in f:
            va = int(float(proposal.get("vehicle_age", 0)))
            return f"Vehicle age {va} years {direction} risk"

        if "experience" in f or f in ("exp_rate", "age_x_exp"):
            exp = int(float(proposal.get("years_exp", 10)))
            return f"Driving experience ({exp} years) {direction} risk"

        if "engine_cc" in f or f == "cc_x_vehicleage":
            cc = int(float(proposal.get("engine_cc", 1500)))
            return f"Engine {cc}CC {direction} risk"

        if "province" in f:
            return f"Province ({proposal.get('province', '')}) claim frequency {direction} risk"

        if "ncb" in f:
            ncb = float(proposal.get("prev_ncb", 0))
            return f"No-Claims Bonus ({ncb:.0f}%) {direction} risk"

        if "blacklist" in f:
            return f"Blacklist status {direction} risk"

        if "sum_insured" in f or f in ("log_si", "si_mv_ratio"):
            return f"Sum insured level {direction} risk"

        if "occupation" in f:
            return f"Occupation ({proposal.get('occupation', '')}) {direction} risk"

        if "gender" in f:
            return f"Gender ({proposal.get('gender', '')}) {direction} risk"

        return f"{feature.replace('_', ' ').title()} {direction} risk"

    # ----------------------------------------------------
    # MAIN CALCULATION (premium + risk)
    # ----------------------------------------------------
    def calculate(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_ready():
            raise RuntimeError("Engine not ready")

        # Primary premium
        rule = self.calc_rule_based_premium(proposal)

        # Risk probability
        if self.risk_pipeline is None or not self.risk_features:
            acc_prob = 0.25  # fallback
        else:
            X = self._row(proposal, self.risk_features)
            try:
                acc_prob = float(self.risk_pipeline.predict_proba(X)[0, 1])
            except Exception:
                acc_prob = 0.25

        risk_score = int(max(0, min(100, round(acc_prob * 100))))
        risk_label = "HIGH" if acc_prob >= 0.5 else "MEDIUM" if acc_prob >= self.optimal_threshold else "LOW"

        # Return (NO explanation injected here — because you said don’t change routes)
        return {
            "risk_score": risk_score,
            "accident_probability_pct": round(acc_prob * 100, 2),
            "risk_label": risk_label,

            "net_premium": int(rule["net_premium"]),
            "base_premium": int(rule.get("base_premium", rule["net_premium"])),
            "ncb_discount": int(rule.get("ncb_discount", 0)),

            "stamp_duty": int(rule["stamp_duty"]),
            "vat": int(rule["vat"]),
            "cess": int(rule["cess"]),
            "gross_premium": int(rule["gross_premium"]),

            "ncb_pct": float(proposal.get("prev_ncb", 0)),
            "rate_pct": None,  # optional: you can compute numeric rate if you want
            "is_insurable": str(proposal.get("is_blacklisted", "No")).strip().lower() not in ("yes", "true", "1"),
            "doc_complete": bool(rule.get("doc_complete", True)),

            "breakdown": {
                "rate_applied": rule.get("rate_applied"),
                "si_used": rule.get("si_used"),
                "si_warning": rule.get("si_warning"),
                "adjustments": rule.get("adjustments", []),
                "net": int(rule["net_premium"]),
                "stamp": int(rule["stamp_duty"]),
                "vat": int(rule["vat"]),
                "cess": int(rule["cess"]),
                "gross": int(rule["gross_premium"]),
            },
        }


_engine: Optional[MotorInsurancePremiumEngine] = None


def get_engine() -> MotorInsurancePremiumEngine:
    global _engine
    if _engine is None:
        _engine = MotorInsurancePremiumEngine()
    return _engine