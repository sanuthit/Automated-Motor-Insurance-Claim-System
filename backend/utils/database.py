
import sqlite3, os, json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "insurance.db"


# ── Schema ─────────────────────────────────────────────────────────────────
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS policies (
    policy_id           TEXT PRIMARY KEY,
    registration_date   TEXT,
    customer_name       TEXT,
    nic                 TEXT,
    driver_age          INTEGER,
    gender              TEXT,
    occupation          TEXT,
    years_exp           INTEGER,
    province            TEXT,
    city                TEXT,
    vehicle_model       TEXT,
    vehicle_year        INTEGER,
    vehicle_age         INTEGER,
    engine_cc           INTEGER,
    vehicle_type        TEXT,
    market_value        REAL,
    sum_insured         REAL,
    previous_insurer    TEXT,
    vehicle_condition   TEXT,
    is_existing_customer TEXT,
    is_blacklisted      TEXT DEFAULT 'No',
    images              TEXT,
    inspection          TEXT,
    fair_value          TEXT,
    financial_interest  TEXT,
    reg_book            TEXT,
    ncb_pct             REAL DEFAULT 0,
    valid_renewal_notice TEXT,
    rebate_approved     TEXT,
    risk_score          INTEGER,
    calculated_premium  REAL,
    status              TEXT DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS renewals (
    renewal_id          TEXT PRIMARY KEY,
    policy_id           TEXT,
    customer_name       TEXT,
    renewal_date        TEXT,
    driver_age          INTEGER,
    gender              TEXT,
    years_with_company  INTEGER,
    vehicle_model       TEXT,
    vehicle_age         INTEGER,
    prev_sum_insured    REAL,
    current_market_value REAL,
    proposed_sum_insured REAL,
    prev_premium        REAL,
    prev_ncb            REAL,
    claims_last_year    INTEGER,
    number_of_claims    INTEGER,
    total_claim_amount  REAL,
    highest_claim_amount REAL,
    days_since_last_claim INTEGER,
    new_ncb             REAL,
    renewal_premium     REAL,
    premium_change_pct  REAL,
    renewal_status      TEXT,
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id            TEXT PRIMARY KEY,
    policy_number       TEXT,
    claim_date          TEXT,
    settlement_date     TEXT,
    vehicle_model       TEXT,
    vehicle_year        INTEGER,
    vehicle_age         INTEGER,
    engine_cc           INTEGER,
    insured_value       REAL,
    province            TEXT,
    claim_type          TEXT,
    claim_amount        REAL,
    approved_amount     REAL,
    claim_status        TEXT,
    driver_age          INTEGER,
    driver_license_years INTEGER,
    at_fault            TEXT,
    previous_claims     INTEGER,
    FOREIGN KEY (policy_number) REFERENCES policies(policy_id)
);

CREATE TABLE IF NOT EXISTS blacklist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nic         TEXT,
    policy_id   TEXT,
    reason      TEXT DEFAULT 'Flagged at registration',
    flagged_date TEXT,
    flagged_by  TEXT DEFAULT 'system',
    is_active   INTEGER DEFAULT 1,
    UNIQUE(nic, policy_id)
);

CREATE TABLE IF NOT EXISTS config (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    note    TEXT
);

CREATE INDEX IF NOT EXISTS idx_policies_nic       ON policies(nic);
CREATE INDEX IF NOT EXISTS idx_claims_policy      ON claims(policy_number);
CREATE INDEX IF NOT EXISTS idx_renewals_policy    ON renewals(policy_id);
CREATE INDEX IF NOT EXISTS idx_blacklist_nic      ON blacklist(nic);
CREATE INDEX IF NOT EXISTS idx_blacklist_policy   ON blacklist(policy_id);
"""

# ── Default config (replaces all hard-coded values in engine.py) ────────────
DEFAULT_CONFIG = {
    "min_rate_pct":         ("0.008",  "Premium floor as % of Sum Insured"),
    "max_rate_pct":         ("0.050",  "Premium cap as % of Sum Insured"),
    "expense_ratio":        ("0.30",   "Admin + commission loading"),
    "profit_margin":        ("0.05",   "Profit loading"),
    "stamp_duty":           ("0.010",  "Statutory stamp duty rate"),
    "vat":                  ("0.060",  "VAT rate"),
    "cess":                 ("0.005",  "CESS rate"),
    "blend_actuarial":      ("0.40",   "Actuarial weight in blended premium"),
    "blend_ml":             ("0.60",   "ML weight in blended premium"),
    "blacklist_surcharge":  ("0.50",   "Surcharge multiplier for blacklisted"),
    "doc_rebate":           ("0.03",   "Rebate for complete docs"),
    "optimal_threshold":    ("0.35",   "Risk classifier decision threshold"),
    "expected_severity":    ("725796", "Average claim severity in LKR (from DS4)"),
    "provinces":            (
        '["Western","Central","Eastern","Northern","North Western","North Central","Uva","Southern","Sabaragamuwa"]',
        "Valid province list"
    ),
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_config(key: str, default=None):
    """Read a single config value from DB."""
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except Exception:
        return row["value"]


def init_db():
    """Create schema + seed config. Idempotent."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        for key, (value, note) in DEFAULT_CONFIG.items():
            conn.execute(
                "INSERT OR IGNORE INTO config(key, value, note) VALUES (?,?,?)",
                (key, value, note)
            )
        conn.commit()
    print(f"DB initialised at {DB_PATH}")


def seed_from_excel(ds1_path, ds3_path, ds4_path):
    """
    Seed policies / renewals / claims / blacklist from Excel files.
    Safe to run multiple times — uses INSERT OR IGNORE.
    """
    import pandas as pd

    with get_connection() as conn:

        # ── Policies (DS1) ────────────────────────────────────────────────
        print("Seeding policies...")
        df1 = pd.read_excel(ds1_path).fillna("")
        inserted_policies = 0
        for _, r in df1.iterrows():
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO policies VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )""", (
                    str(r.get("Policy_ID","")),
                    str(r.get("Registration_Date",""))[:10],
                    str(r.get("Customer_Name","")),
                    str(r.get("NIC","")),
                    int(r.get("Driver_Age", 35) or 35),
                    str(r.get("Gender","Male")),
                    str(r.get("Occupation","Other")),
                    int(r.get("Years_of_Driving_Experience", 5) or 5),
                    str(r.get("Province","Western")),
                    str(r.get("City","")),
                    str(r.get("Vehicle_Model","")),
                    int(r.get("Vehicle_Year", 2020) or 2020),
                    int(r.get("Vehicle_Age_Years", 3) or 3),
                    int(r.get("Engine_CC", 1500) or 1500),
                    str(r.get("Vehicle_Type","Car")),
                    float(r.get("Market_Value_LKR", 0) or 0),
                    float(r.get("Proposed_Sum_Insured_LKR", 0) or 0),
                    str(r.get("Previous_Insurer","")),
                    str(r.get("Vehicle_Condition","Good")),
                    str(r.get("Is_Existing_Customer","No")),
                    str(r.get("Is_Blacklisted","No")),
                    str(r.get("Images_Uploaded","No")),
                    str(r.get("Inspection_Report_Uploaded","No")),
                    str(r.get("Fair_Value_Proposed","No")),
                    str(r.get("Financial_Interest_Recorded","No")),
                    str(r.get("Registration_Book_Available","No")),
                    float(r.get("NCB_Claimed_Percentage", 0) or 0),
                    str(r.get("Valid_Renewal_Notice","No")),
                    str(r.get("Rebate_Approved","No")),
                    int(r.get("Risk_Score", 50) or 50),
                    float(r.get("Calculated_Premium_LKR", 0) or 0),
                    "Active",
                ))
                inserted_policies += 1

                # Auto-populate blacklist table
                if str(r.get("Is_Blacklisted","No")).strip() == "Yes":
                    conn.execute("""
                        INSERT OR IGNORE INTO blacklist(nic, policy_id, reason, flagged_date)
                        VALUES (?,?,?,?)
                    """, (
                        str(r.get("NIC","")),
                        str(r.get("Policy_ID","")),
                        "Flagged at registration",
                        str(r.get("Registration_Date",""))[:10],
                    ))
            except Exception as e:
                pass  # skip bad rows silently
        print(f"  Inserted {inserted_policies} policies")

        # ── Renewals (DS3) ────────────────────────────────────────────────
        print("Seeding renewals...")
        df3 = pd.read_excel(ds3_path).fillna(0)
        inserted_renewals = 0
        for _, r in df3.iterrows():
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO renewals VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )""", (
                    str(r.get("Renewal_ID","")),
                    str(r.get("Original_Policy_ID","")),
                    str(r.get("Customer_Name","")),
                    str(r.get("Renewal_Date",""))[:10],
                    int(r.get("Driver_Age", 35) or 35),
                    str(r.get("Gender","Male")),
                    int(r.get("Years_With_Company", 1) or 1),
                    str(r.get("Vehicle_Model","")),
                    int(r.get("Vehicle_Current_Age", 3) or 3),
                    float(r.get("Previous_Sum_Insured_LKR", 0) or 0),
                    float(r.get("Current_Market_Value_LKR", 0) or 0),
                    float(r.get("Proposed_Sum_Insured_LKR", 0) or 0),
                    float(r.get("Previous_Premium_LKR", 0) or 0),
                    float(r.get("Previous_NCB_Percentage", 0) or 0),
                    int(r.get("Claims_Last_Year", 0) or 0),
                    int(r.get("Number_of_Claims", 0) or 0),
                    float(r.get("Total_Claim_Amount_Last_Year_LKR", 0) or 0),
                    float(r.get("Highest_Claim_Amount_LKR", 0) or 0),
                    int(r.get("Days_Since_Last_Claim", 999) or 999),
                    float(r.get("New_NCB_Percentage", 0) or 0),
                    float(r.get("Calculated_Renewal_Premium_LKR", 0) or 0),
                    float(r.get("Premium_Change_Percentage", 0) or 0),
                    str(r.get("Renewal_Status","Pending")),
                ))
                inserted_renewals += 1
            except Exception:
                pass
        print(f"  Inserted {inserted_renewals} renewals")

        # ── Claims (DS4) ──────────────────────────────────────────────────
        print("Seeding claims...")
        df4 = pd.read_excel(ds4_path).fillna(0)
        inserted_claims = 0
        for _, r in df4.iterrows():
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO claims VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )""", (
                    str(r.get("Claim_ID","")),
                    str(r.get("Policy_Number","")),
                    str(r.get("Claim_Date",""))[:10],
                    str(r.get("Settlement_Date",""))[:10],
                    str(r.get("Vehicle_Model","")),
                    int(r.get("Vehicle_Year", 2020) or 2020),
                    int(r.get("Vehicle_Age_Years", 3) or 3),
                    int(r.get("Engine_CC", 1500) or 1500),
                    float(r.get("Insured_Value_LKR", 0) or 0),
                    str(r.get("Province","Western")),
                    str(r.get("Claim_Type","Accidental Damage")),
                    float(r.get("Claim_Amount_LKR", 0) or 0),
                    float(r.get("Approved_Amount_LKR", 0) or 0),
                    str(r.get("Claim_Status","Pending")),
                    int(r.get("Driver_Age", 35) or 35),
                    int(r.get("Driver_License_Years", 5) or 5),
                    str(r.get("At_Fault","No")),
                    int(r.get("Previous_Claims", 0) or 0),
                ))
                inserted_claims += 1
            except Exception:
                pass
        print(f"  Inserted {inserted_claims} claims")
        conn.commit()

    print(f"\nSeeding complete. DB at: {DB_PATH}")


# ── Lookup helpers used by API routes ──────────────────────────────────────
def get_policy(policy_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM policies WHERE policy_id=?", (policy_id,)
        ).fetchone()
    return dict(row) if row else None


def get_policy_claims(policy_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM claims WHERE policy_number=? ORDER BY claim_date DESC",
            (policy_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_latest_renewal(policy_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM renewals WHERE policy_id=? ORDER BY renewal_date DESC LIMIT 1",
            (policy_id,)
        ).fetchone()
    return dict(row) if row else None


def check_blacklist(nic: str = None, policy_id: str = None) -> dict:
    with get_connection() as conn:
        if nic:
            row = conn.execute(
                "SELECT * FROM blacklist WHERE nic=? AND is_active=1 LIMIT 1", (nic,)
            ).fetchone()
        elif policy_id:
            row = conn.execute(
                "SELECT * FROM blacklist WHERE policy_id=? AND is_active=1 LIMIT 1", (policy_id,)
            ).fetchone()
        else:
            return {"blacklisted": False}
    if row:
        return {"blacklisted": True, "reason": row["reason"], "flagged_date": row["flagged_date"]}
    return {"blacklisted": False}


def get_dashboard_stats() -> dict:
    with get_connection() as conn:
        total  = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM policies WHERE status='Active'").fetchone()[0]
        claims = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        bl     = conn.execute("SELECT COUNT(*) FROM blacklist WHERE is_active=1").fetchone()[0]
        avg_p  = conn.execute("SELECT AVG(calculated_premium) FROM policies WHERE calculated_premium>0").fetchone()[0]
        high_r = conn.execute("SELECT COUNT(*) FROM policies WHERE risk_score>=70").fetchone()[0]
    return {
        "total_policies": total,
        "active_policies": active,
        "total_claims": claims,
        "blacklisted_count": bl,
        "avg_premium": round(avg_p or 0, 2),
        "high_risk_count": high_r,
    }


# ── CLI seed runner ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Adjust these paths as needed
    base = Path(__file__).resolve().parents[2] / "data"
    ds1  = base / "DS1_new_policy_registration_FIXED.xlsx"
    ds3  = base / "DS3_policy_renewal_FIXED.xlsx"
    ds4  = base / "DS4_claims_FIXED.xlsx"

    # If paths provided as args, use them
    if len(sys.argv) == 4:
        ds1, ds3, ds4 = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

    init_db()
    seed_from_excel(ds1, ds3, ds4)
