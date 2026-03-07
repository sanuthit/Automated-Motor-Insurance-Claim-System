from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal, Any
from enum import Enum


class Province(str, Enum):
    WESTERN      = "Western"
    CENTRAL      = "Central"
    EASTERN      = "Eastern"
    NORTHERN     = "Northern"
    NORTH_WESTERN = "North Western"
    NORTH_CENTRAL = "North Central"
    UVA          = "Uva"
    SOUTHERN     = "Southern"
    SABARAGAMUWA = "Sabaragamuwa"


class VehicleType(str, Enum):
    CAR  = "Car"
    SUV  = "SUV"
    VAN  = "Van"
    DUAL = "Dual Purpose"
    # Motor Cycle removed — not in database


class Gender(str, Enum):
    MALE   = "Male"
    FEMALE = "Female"
    # Other removed — not in database


class VehicleCondition(str, Enum):
    EXCELLENT = "Excellent"
    GOOD      = "Good"
    FAIR      = "Fair"
    POOR      = "Poor"


class ClaimPattern(str, Enum):
    NO_CLAIMS = "No Claims"
    SINGLE    = "Single Claim"
    MULTIPLE  = "Multiple Claims"
    FREQUENT  = "Frequent Claimant"


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool): return v
    if isinstance(v, int):  return bool(v)
    if isinstance(v, str):  return v.strip().lower() in ("yes", "true", "1")
    return False


class PolicyRequest(BaseModel):
    customer_name:        str
    nic:                  str
    driver_age:           int = Field(..., ge=18, le=80)
    gender:               Gender = Gender.MALE
    occupation:           str = "Employed"
    years_exp:            int = Field(default=0, ge=0, le=60)
    province:             Province = Province.WESTERN
    city:                 Optional[str] = ""
    is_existing_customer: Any = False
    is_blacklisted:       Any = False
    vehicle_model:        str
    vehicle_year:         int = Field(default=2015, ge=1980, le=2026)
    vehicle_type:         VehicleType = VehicleType.CAR
    engine_cc:            int = Field(default=1500, ge=50, le=8000)
    vehicle_condition:    VehicleCondition = VehicleCondition.GOOD
    market_value:         int = Field(default=1000000, gt=0)
    sum_insured:          int = Field(default=1000000, gt=0)
    previous_insurer:     Optional[str] = "None"
    prev_ncb:             int = Field(default=0, ge=0, le=50)
    valid_renewal_notice: Any = False
    images:               Any = True
    inspection:           Any = True
    fair_value:           Any = True
    financial_interest:   Any = True
    reg_book:             Any = True
    rebate_approved:      Any = False
    vehicle_age:          Optional[int] = None

    @model_validator(mode="after")
    def coerce_booleans(self):
        for f in ("is_existing_customer","is_blacklisted","valid_renewal_notice",
                  "images","inspection","fair_value","financial_interest","reg_book","rebate_approved"):
            setattr(self, f, _to_bool(getattr(self, f)))
        return self

    @field_validator("sum_insured")
    @classmethod
    def validate_si(cls, v, info):
        mv = info.data.get("market_value")
        if mv and v > mv * 1.25:
            raise ValueError(f"Sum insured cannot exceed 125% of market value (max: {int(mv*1.25):,})")
        return v


class PremiumResponse(BaseModel):
    risk_score:               int
    accident_probability_pct: float
    risk_label:               Literal["LOW","MEDIUM","HIGH"]
    net_premium:              int
    base_premium:             Optional[int] = None
    ncb_discount:             Optional[int] = None
    stamp_duty:               int
    vat:                      int
    cess:                     int
    gross_premium:            int
    ncb_pct:                  float
    rate_pct:                 Optional[float] = None
    is_insurable:             bool
    doc_complete:             bool
    breakdown:                dict
    explanation:              Optional[dict] = None


class RenewalRequest(BaseModel):
    policy_id:             str
    customer_name:         str
    driver_age:            int = Field(..., ge=18, le=80)
    vehicle_model:         str
    vehicle_current_age:   int
    previous_sum_insured:  int
    current_market_value:  int
    proposed_sum_insured:  int
    previous_premium:      int
    previous_ncb:          int = Field(default=0, ge=0, le=50)
    new_ncb:               int = Field(default=0, ge=0, le=50)
    claims_last_year:      int = Field(default=0, ge=0)
    number_of_claims:      int = Field(default=0, ge=0)
    total_claim_amount:    int = Field(default=0, ge=0)
    claim_pattern:         ClaimPattern = ClaimPattern.NO_CLAIMS
    highest_claim_amount:  int = Field(default=0, ge=0)
    days_since_last_claim: int = Field(default=999, ge=0)
    years_with_company:    int = Field(default=1, ge=0)
    sum_insured_inline:    bool = True
    gender:                Gender = Gender.MALE


class RenewalResponse(BaseModel):
    previous_premium:   int
    renewal_premium:    int
    premium_change_pct: float
    new_ncb:            int
    recommendation:     Literal["APPROVE","REVIEW","REJECT"]
    risk_factors:       list
    breakdown:          dict


class ClaimRequest(BaseModel):
    policy_number:           str
    vehicle_model:           Optional[str] = ""
    vehicle_year:            Optional[int] = 2015
    engine_cc:               Optional[int] = 1500
    insured_value:           int
    province:                Province = Province.WESTERN
    claim_type:              str
    claim_amount_lkr:        Optional[int] = Field(default=None, ge=1000, description="Minimum LKR 1,000")
    claim_amount:            Optional[int] = Field(default=None, ge=1000, description="Minimum LKR 1,000")
    driver_age:              int = Field(..., ge=18, le=80)
    vehicle_age:             Optional[int] = 5
    driver_license_years:    Optional[int] = 5
    previous_claims:         int = 0
    at_fault:                Optional[bool] = None
    accident_date:           Optional[str] = None
    accident_location:       Optional[str] = None
    accident_description:    Optional[str] = None
    accident_severity:       Optional[str] = "Minor"
    third_party_involved:    Any = False
    police_report_available: Any = False
    witness_available:       Any = False

    @model_validator(mode="after")
    def normalise(self):
        if self.claim_amount is None and self.claim_amount_lkr is not None:
            self.claim_amount = self.claim_amount_lkr
        elif self.claim_amount_lkr is None and self.claim_amount is not None:
            self.claim_amount_lkr = self.claim_amount
        if self.claim_amount is None:
            self.claim_amount = 0
        for f in ("third_party_involved","police_report_available","witness_available"):
            setattr(self, f, _to_bool(getattr(self, f)))
        return self


class ClaimResponse(BaseModel):
    claim_id:        str
    claim_status:    Literal["Approved","Pending Review","Requires Investigation"]
    approved_amount: int
    deductible:      int
    recommendation:  str
    risk_flags:      list
    risk_score:      Optional[int] = None
    risk_note:       Optional[str] = None
    processing_days: Optional[int] = None


class DashboardStats(BaseModel):
    total_policies:      int
    avg_premium:         float
    claim_approval_rate: float
    avg_claim_amount:    float
    ncb_rate:            float
    accident_rate:       float
    model_auc:           float
    model_r2:            float
