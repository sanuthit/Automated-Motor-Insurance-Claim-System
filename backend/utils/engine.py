"""
engine.py  —  backend/utils/engine.py
Real Sri Lanka comprehensive motor insurance premium rates (2024)
"""

import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"


class MotorInsurancePremiumEngine:

    STAMP_DUTY = 0.010
    VAT = 0.080
    CESS = 0.005

    VEHICLE_BASE_RATES = {
        "Car": 0.030,
        "SUV": 0.035,
        "Van": 0.040,
        "Dual Purpose": 0.032,
    }

    AGE_LOADING = {
        0: 0.000,
        1: 0.002,
        2: 0.003,
        3: 0.005,
        4: 0.007,
        5: 0.010,
        6: 0.012,
        7: 0.015,
        8: 0.018,
        9: 0.020,
    }

    MIN_PREMIUM = 15000
    MAX_SI_RATIO = 1.10
    MIN_SI_RATIO = 0.90

    BLEND_ACTUARIAL = 0.35
    BLEND_ML = 0.65

    def __init__(self):

        self.risk_pipeline = None
        self.prem_pipeline = None
        self.renew_pipeline = None

        self.risk_features = []
        self.prem_features = []
        self.renew_features = []

        self.expected_severity = 725796
        self.optimal_threshold = 0.35

        self._ready = False

        self._load()

    # ----------------------------------------------------
    # LOAD ML MODELS
    # ----------------------------------------------------

    def _load(self):

        pipe_path = MODEL_DIR / "pipeline_artifacts.pkl"

        if pipe_path.exists():

            print("Loading pipeline artifacts...")

            with open(pipe_path, "rb") as f:
                arts = pickle.load(f)

            # ---- risk model ----
            risk_block = arts.get("risk") or arts.get("risk_model") or arts.get("risk_pipeline")

            if isinstance(risk_block, dict):

                self.risk_pipeline = (
                    risk_block.get("pipeline")
                    or risk_block.get("model")
                    or risk_block.get("clf")
                )

                self.risk_features = (
                    risk_block.get("features")
                    or risk_block.get("feature_list")
                    or []
                )

            else:

                self.risk_pipeline = (
                    arts.get("risk_pipeline")
                    or arts.get("pipeline")
                    or arts.get("model")
                    or arts.get("clf")
                )

                self.risk_features = (
                    arts.get("risk_features")
                    or arts.get("features")
                    or arts.get("feature_list")
                    or []
                )

            # ---- premium model ----
            prem_block = arts.get("premium")

            if isinstance(prem_block, dict):

                self.prem_pipeline = (
                    prem_block.get("pipeline") or prem_block.get("model")
                )

                self.prem_features = (
                    prem_block.get("features")
                    or prem_block.get("feature_list")
                    or []
                )

            # ---- renewal model ----
            renew_block = arts.get("renewal")

            if isinstance(renew_block, dict):

                self.renew_pipeline = (
                    renew_block.get("pipeline") or renew_block.get("model")
                )

                self.renew_features = (
                    renew_block.get("features")
                    or renew_block.get("feature_list")
                    or []
                )

            print("Model artifacts loaded successfully")

            self._ready = True

            if self.risk_pipeline is None:
                print("WARNING: risk_pipeline not found in artifacts")

            return

        # --------------------------------------------------
        # LEGACY MODEL FALLBACK
        # --------------------------------------------------

        rc_path = MODEL_DIR / "risk_classifier.pkl"
        rm_path = MODEL_DIR / "regression_models.pkl"

        if rc_path.exists() and rm_path.exists():

            print("Loading legacy models...")

            with open(rc_path, "rb") as f:
                rc = pickle.load(f)

            with open(rm_path, "rb") as f:
                rm = pickle.load(f)

            self.risk_pipeline = rc["model"]
            self.risk_features = rc.get("features", [])

            self.prem_pipeline = rm["premium"]["model"]
            self.prem_features = rm["premium"]["features"]

            self._ready = True

            print("Legacy models loaded")

        else:

            print("No ML models found. System will run rule-based premium only.")
            self._ready = True

    # ----------------------------------------------------
    # STATUS
    # ----------------------------------------------------

    def is_ready(self):
        return self._ready

    # ----------------------------------------------------
    # RULE BASED PREMIUM ENGINE
    # ----------------------------------------------------

    def calc_rule_based_premium(self, proposal):

        mv = float(proposal.get("market_value", 1000000))
        si = float(proposal.get("sum_insured", mv))

        vt = str(proposal.get("vehicle_type", "Car"))
        va = int(proposal.get("vehicle_age", 0))

        ncb = float(proposal.get("prev_ncb", 0))

        base_rate = self.VEHICLE_BASE_RATES.get(vt, 0.03)
        age_load = self.AGE_LOADING.get(min(va, 9), 0.02)

        total_rate = base_rate + age_load

        net = si * total_rate

        if ncb > 0:
            net = net * (1 - ncb / 100)

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
            "rate_applied": total_rate,
            "doc_complete": True,
            "adjustments": [],
        }

    # ----------------------------------------------------
    # FEATURE BUILDING
    # ----------------------------------------------------

    def _raw_dict(self, p):

        return {
            "Driver_Age": float(p.get("driver_age", 35)),
            "Engine_CC": float(p.get("engine_cc", 1500)),
            "Vehicle_Age_Years": float(p.get("vehicle_age", 5)),
            "Sum_Insured_LKR": float(p.get("sum_insured", 1000000)),
        }

    def _row(self, proposal, feats):

        d = self._raw_dict(proposal)

        return pd.DataFrame([[d.get(f, 0.0) for f in feats]], columns=feats)

    # ----------------------------------------------------
    # MAIN CALCULATION
    # ----------------------------------------------------

    def calculate(self, proposal):

        if not self.is_ready():
            raise RuntimeError("Engine not ready")

        rule = self.calc_rule_based_premium(proposal)

        # if ML not available -> rule only
        if self.risk_pipeline is None or not self.risk_features:

            acc_prob = 0.25

        else:

            X = self._row(proposal, self.risk_features)

            acc_prob = float(self.risk_pipeline.predict_proba(X)[0, 1])

        risk_score = int(acc_prob * 100)

        risk_label = (
            "HIGH"
            if acc_prob >= 0.5
            else "MEDIUM"
            if acc_prob >= self.optimal_threshold
            else "LOW"
        )

        net = rule["net_premium"]

        stamp = int(net * self.STAMP_DUTY)
        vat = int(net * self.VAT)
        cess = int(net * self.CESS)

        gross = net + stamp + vat + cess

        return {

            "risk_score": risk_score,

            "accident_probability_pct": round(acc_prob * 100, 2),

            "risk_label": risk_label,

            "net_premium": net,

            "stamp_duty": stamp,

            "vat": vat,

            "cess": cess,

            "gross_premium": gross,

            "doc_complete": rule["doc_complete"],

            "breakdown": {
                "net": net,
                "stamp": stamp,
                "vat": vat,
                "cess": cess,
                "gross": gross,
            },
        }


_engine: Optional[MotorInsurancePremiumEngine] = None


def get_engine() -> MotorInsurancePremiumEngine:

    global _engine

    if _engine is None:
        _engine = MotorInsurancePremiumEngine()

    return _engine