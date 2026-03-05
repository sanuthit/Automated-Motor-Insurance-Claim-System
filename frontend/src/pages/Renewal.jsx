import { useState } from "react";
import insuranceAPI from "../services/api";

const safe = (e) => {
  if (!e) return "Unknown error — check backend is running on port 8000";
  const d = e?.response?.data;
  if (d?.detail) return typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
  if (typeof e?.message === "string") return e.message;
  return "Request failed";
};

const fmt = (n) =>
  `Rs. ${Number(n || 0).toLocaleString("en-LK", { maximumFractionDigits: 0 })}`;

function RiskGauge({ score }) {
  if (score == null) return null;
  const level = score < 25 ? "Low" : score < 50 ? "Moderate" : score < 70 ? "High" : "Very High";
  const color = score < 25 ? "#16a34a" : score < 50 ? "#f59e0b" : score < 70 ? "#ea580c" : "#dc2626";
  return (
    <div style={{ textAlign: "center", padding: 16 }}>
      <svg width={140} height={140} viewBox="0 0 140 140">
        <circle cx={70} cy={70} r={55} fill="none" stroke="#f1f5f9" strokeWidth={13} />
        <circle cx={70} cy={70} r={55} fill="none" stroke={color} strokeWidth={13}
          strokeDasharray={`${(score / 100) * 346} 346`}
          strokeLinecap="round" transform="rotate(-90 70 70)" />
        <text x={70} y={66} textAnchor="middle" fontSize={28} fontWeight={700} fill={color}>{score}</text>
        <text x={70} y={84} textAnchor="middle" fontSize={11} fill="#64748b">{level} Risk</text>
      </svg>
    </div>
  );
}

function ShapPanel({ explanation }) {
  if (!explanation?.available || !explanation?.top_drivers?.length) return null;
  return (
    <div style={{ padding: "14px 16px" }}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>Why this risk score?</div>
      {explanation.top_drivers.map((d, i) => {
        const isRisk = d.direction === "increases_risk";
        const barW = d.magnitude === "high" ? 70 : d.magnitude === "medium" ? 44 : 20;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 9 }}>
            <span style={{ color: isRisk ? "#dc2626" : "#16a34a", fontWeight: 700, width: 14 }}>
              {isRisk ? "+" : "-"}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                <span style={{ fontSize: 12, fontWeight: 500 }}>
                  {String(d.feature || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                </span>
                <span style={{ fontSize: 11, color: isRisk ? "#dc2626" : "#16a34a" }}>
                  {d.reason || (isRisk ? "Increases risk" : "Reduces risk")}
                </span>
              </div>
              <div style={{ height: 5, background: "#f1f5f9", borderRadius: 3 }}>
                <div style={{ height: 5, borderRadius: 3, width: `${barW}%`,
                  background: isRisk ? "#dc2626" : "#16a34a" }} />
              </div>
            </div>
            <span style={{ fontSize: 11, fontFamily: "monospace", width: 48, textAlign: "right",
              color: isRisk ? "#dc2626" : "#16a34a" }}>
              {Number(d.shap_value) > 0 ? "+" : ""}{Number(d.shap_value).toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function Renewal() {
  const [searchId, setSearchId]         = useState("");
  const [fetchLoading, setFetchLoading] = useState(false);
  const [fetchErr, setFetchErr]         = useState("");
  const [policy, setPolicy]             = useState(null);
  const [claims, setClaims]             = useState([]);
  const [newSI, setNewSI]               = useState("");
  const [newNCB, setNewNCB]             = useState(0);
  const [errs, setErrs]                 = useState({});
  const [calcLoading, setCalcLoading]   = useState(false);
  const [calcErr, setCalcErr]           = useState("");
  const [result, setResult]             = useState(null);
  const [renewLoading, setRenewLoading] = useState(false);
  const [renewErr, setRenewErr]         = useState("");
  const [renewed, setRenewed]           = useState(null);

  const fetchPolicy = async () => {
    if (!searchId.trim()) { setFetchErr("Please enter a Policy ID"); return; }
    setFetchLoading(true); setFetchErr(""); setPolicy(null); setResult(null);
    try {
      const res = await insuranceAPI.getRenewalPolicy(searchId.trim().toUpperCase());
      const d = res.data;

      // Normalise: API may return nested {policy:{}, vehicle:{}, ...} or flat
      let flat = {};
      if (d.policy && typeof d.policy === "object") {
        flat = {
          ...d.policy,
          ...(d.vehicle || {}),
          ...(d.current_policy || {}),
          ...(d.suggested_renewal || {}),
          // Map to display keys
          current_market_value_lkr:  d.vehicle?.market_value,
          previous_premium_lkr:      d.suggested_renewal?.previous_premium || d.current_policy?.calculated_premium,
          previous_ncb_percentage:   d.suggested_renewal?.previous_ncb ?? d.current_policy?.ncb_pct,
          suggested_new_ncb:         d.suggested_renewal?.new_ncb,
          vehicle_current_age:       d.vehicle?.vehicle_age,
          years_of_driving_experience: d.policy?.years_exp,
          years_with_company:        d.suggested_renewal?.years_with_company,
          claims:                    d.claim_history?.claims || [],
          total_claims:              d.claim_history?.total_claims || 0,
          blacklisted:               d.blacklist?.blacklisted || false,
        };
      } else {
        flat = { ...d };
        flat.claims = d.claims || [];
      }

      setPolicy(flat);
      setClaims(flat.claims || []);
      setNewSI(String(Math.round(
        flat.proposed_sum_insured || flat.current_market_value_lkr || flat.market_value || flat.sum_insured || 1000000
      )));
      setNewNCB(flat.suggested_new_ncb ?? flat.new_ncb_percentage ?? flat.previous_ncb_percentage ?? 0);
    } catch (e) {
      setFetchErr(safe(e));
    } finally {
      setFetchLoading(false);
    }
  };

  const calculate = async () => {
    const e = {};
    const si = Number(newSI);
    const mv = Number(policy?.current_market_value_lkr || policy?.market_value || 0);
    if (!newSI || si < 100000) e.newSI = "Minimum Sum Insured: Rs. 100,000";
    else if (mv && si > mv * 1.25) e.newSI = `Cannot exceed 125% of market value (${fmt(mv * 1.25)})`;
    if (Object.keys(e).length) { setErrs(e); return; }
    setErrs({});
    setCalcLoading(true); setCalcErr(""); setResult(null);
    try {
      const res = await insuranceAPI.calculateRenewal({
        policy_id:             policy.policy_id || policy.original_policy_id || searchId.trim().toUpperCase(),
        proposed_sum_insured:  si,
        new_ncb:               Number(newNCB),
        current_market_value:  mv || undefined,
        years_with_company:    policy.years_with_company || undefined,
      });
      setResult(res.data);
    } catch (e) {
      setCalcErr(safe(e));
    } finally {
      setCalcLoading(false);
    }
  };

  const renewPolicy = async () => {
    if (!result) return;
    setRenewLoading(true); setRenewErr(""); setRenewed(null);
    try {
      const res = await insuranceAPI.processRenewal({
        policy_id:            policy.policy_id || searchId.trim().toUpperCase(),
        renewal_premium:      result.renewal_premium || result.gross_premium,
        new_ncb:              Number(result.new_ncb ?? newNCB),
        proposed_sum_insured: Number(newSI),
      });
      setRenewed(res.data);
    } catch (e) {
      setRenewErr(safe(e));
    } finally {
      setRenewLoading(false);
    }
  };(
    (c.claim_status || "").toLowerCase().includes("approv") ||
    Number(c.approved_amount_lkr || c.approved_amount || 0) > 0
);
  const totalApproved  = approvedClaims.reduce((s, c) => s + Number(c.approved_amount_lkr || c.approved_amount || c.claim_amount || 0), 0);
  const approvedCount  = approvedClaims.length;

  return (
    <div style={{ padding: 24, fontFamily: "'Segoe UI',sans-serif", background: "#f8fafc", minHeight: "100vh" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f172a", margin: "0 0 4px" }}>Policy Renewal</h1>
      <p style={{ color: "#64748b", marginTop: 0, marginBottom: 24 }}>
        Search by Policy ID — details loaded from the database automatically
      </p>

      {/* Search */}
      <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)", marginBottom: 20 }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: "#334155", display: "block", marginBottom: 8 }}>Policy ID</label>
        <div style={{ display: "flex", gap: 10 }}>
          <input value={searchId} onChange={e => { setSearchId(e.target.value); setFetchErr(""); }}
            onKeyDown={e => e.key === "Enter" && fetchPolicy()}
            placeholder="e.g. NP00045355"
            style={{ flex: 1, padding: "10px 14px", borderRadius: 8,
              border: `1px solid ${fetchErr ? "#dc2626" : "#e2e8f0"}`, fontSize: 14 }} />
          <button onClick={fetchPolicy} disabled={fetchLoading}
            style={{ padding: "10px 24px", borderRadius: 8, border: "none", background: "#2563eb",
              color: "#fff", fontWeight: 600, cursor: fetchLoading ? "not-allowed" : "pointer",
              opacity: fetchLoading ? 0.7 : 1 }}>
            {fetchLoading ? "Searching..." : "Fetch Policy"}
          </button>
        </div>
        {fetchErr && <p style={{ color: "#dc2626", fontSize: 12, marginTop: 6 }}>&#9888; {fetchErr}</p>}
      </div>

      {policy && (
        <>
          {/* Customer + Vehicle grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
            <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
              <h3 style={{ margin: "0 0 14px", fontSize: 14, fontWeight: 700 }}>Customer & Policy</h3>
              {[
                ["Policy ID",          policy.policy_id || searchId],
                ["Customer",           policy.customer_name],
                ["NIC",                policy.nic],
                ["Province",           policy.province],
                ["Years with Company", policy.years_with_company != null ? policy.years_with_company + " yrs" : "—"],
                ["Previous Premium",   fmt(policy.previous_premium_lkr || policy.calculated_premium || policy.previous_premium)],
                ["Previous NCB",       (policy.previous_ncb_percentage ?? policy.ncb_pct ?? 0) + "%"],
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #f8fafc", fontSize: 13 }}>
                  <span style={{ color: "#64748b" }}>{k}</span>
                  <span style={{ fontWeight: 600, color: "#0f172a" }}>{v || "—"}</span>
                </div>
              ))}
            </div>
            <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
              <h3 style={{ margin: "0 0 14px", fontSize: 14, fontWeight: 700 }}>Vehicle Details</h3>
              {[
                ["Model",         policy.vehicle_model],
                ["Year",          policy.vehicle_year],
                ["Engine CC",     policy.engine_cc != null ? policy.engine_cc + " cc" : "—"],
                ["Type",          policy.vehicle_type],
                ["Condition",     policy.vehicle_condition],
                ["Vehicle Age",   (policy.vehicle_current_age ?? policy.vehicle_age) != null ? (policy.vehicle_current_age ?? policy.vehicle_age) + " yrs" : "—"],
                ["Market Value",  fmt(policy.current_market_value_lkr || policy.market_value)],
                ["Previous SI",   fmt(policy.sum_insured || policy.previous_sum_insured_lkr)],
                ["Driver Age",    policy.driver_age != null ? policy.driver_age + " yrs" : "—"],
                ["Experience",    (policy.years_of_driving_experience ?? policy.years_exp) != null
                  ? (policy.years_of_driving_experience ?? policy.years_exp) + " yrs" : "—"],
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #f8fafc", fontSize: 13 }}>
                  <span style={{ color: "#64748b" }}>{k}</span>
                  <span style={{ fontWeight: 600, color: "#0f172a" }}>{v || "—"}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Claims */}
          {claims.length > 0 ? (
            <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)", marginBottom: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>Claims History ({claims.length})</h3>
                <div style={{ display: "flex", gap: 10 }}>
                  <span style={{ fontSize: 12, padding: "3px 10px", background: "#fef2f2", color: "#dc2626", borderRadius: 20, fontWeight: 600 }}>
                    {approvedCount} Approved
                  </span>
                  <span style={{ fontSize: 12, padding: "3px 10px", background: "#fef2f2", color: "#dc2626", borderRadius: 20, fontWeight: 600 }}>
                    Total: {fmt(totalApproved)}
                  </span>
                </div>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "#f8fafc" }}>
                    {["Claim ID","Type","Date","Claimed","Approved","Status"].map(h => (
                      <th key={h} style={{ padding: "7px 10px", textAlign: "left", fontWeight: 600, color: "#475569" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {claims.slice(0, 6).map((c, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "7px 10px" }}>{c.claim_id || "CLM-" + (i + 1)}</td>
                      <td style={{ padding: "7px 10px" }}>{c.claim_type || "—"}</td>
                      <td style={{ padding: "7px 10px" }}>{c.claim_date || "—"}</td>
                      <td style={{ padding: "7px 10px" }}>{fmt(c.claim_amount_lkr || c.claim_amount)}</td>
                      <td style={{ padding: "7px 10px", fontWeight: 600 }}>{fmt(c.approved_amount_lkr || c.approved_amount)}</td>
                      <td style={{ padding: "7px 10px" }}>
                        <span style={{ padding: "2px 8px", borderRadius: 12, fontSize: 11, fontWeight: 600,
                          background: (c.claim_status || "").toLowerCase().includes("approv") ? "#dcfce7" : "#fef9c3",
                          color: (c.claim_status || "").toLowerCase().includes("approv") ? "#166534" : "#854d0e" }}>
                          {c.claim_status || "Unknown"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 10,
              padding: "12px 16px", marginBottom: 20, color: "#166534", fontSize: 13 }}>
              No claims recorded — eligible for maximum NCB discount
            </div>
          )}

          {/* Renewal params */}
          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)", marginBottom: 20 }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 14, fontWeight: 700 }}>Renewal Parameters</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: "#334155", display: "block", marginBottom: 6 }}>
                  New Sum Insured (LKR) *
                </label>
                <input type="number" value={newSI}
                  onChange={e => { setNewSI(e.target.value); setErrs(p => ({ ...p, newSI: "" })); }}
                  style={{ width: "100%", padding: "10px 14px", borderRadius: 8,
                    border: `1px solid ${errs.newSI ? "#dc2626" : "#e2e8f0"}`, fontSize: 14, boxSizing: "border-box" }} />
                {errs.newSI && <p style={{ color: "#dc2626", fontSize: 12, marginTop: 4 }}>&#9888; {errs.newSI}</p>}
                {(policy.current_market_value_lkr || policy.market_value) > 0 && (
                  <p style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
                    Market value: {fmt(policy.current_market_value_lkr || policy.market_value)}
                  </p>
                )}
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: "#334155", display: "block", marginBottom: 6 }}>
                  New NCB (%)
                </label>
                <select value={newNCB} onChange={e => setNewNCB(Number(e.target.value))}
                  style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 14 }}>
                  {(approvedCount > 0 ? [0, 10, 20] : [0, 10, 20, 30, 40, 50]).map(v => (
                    <option key={v} value={v}>{v}%</option>
                  ))}
                </select>
                {approvedCount > 0 && (
                  <p style={{ fontSize: 11, color: "#ea580c", marginTop: 4 }}>
                    &#9888; {approvedCount} claim(s) — NCB capped at 20%
                  </p>
                )}
              </div>
            </div>
            <div style={{ marginTop: 12, padding: "10px 14px", background: "#f8fafc", borderRadius: 8, fontSize: 12, color: "#64748b" }}>
              <strong>Renewal period:</strong> Today to {new Date(Date.now() + 365 * 86400000).toLocaleDateString("en-LK")}
              {" | "}
              <strong>Loading:</strong> {approvedCount === 0 ? "None (no claims)" : approvedCount === 1 ? "15-35% surcharge" : "50-80% surcharge"}
            </div>
            <button onClick={calculate} disabled={calcLoading}
              style={{ marginTop: 16, padding: "12px 28px", borderRadius: 8, border: "none",
                background: calcLoading ? "#94a3b8" : "#2563eb", color: "#fff",
                fontWeight: 700, fontSize: 15, cursor: calcLoading ? "not-allowed" : "pointer" }}>
              {calcLoading ? "Calculating..." : "Calculate Renewal Premium"}
            </button>
            {calcErr && (
              <div style={{ marginTop: 12, padding: "10px 14px", background: "#fef2f2",
                border: "1px solid #fca5a5", borderRadius: 8, color: "#dc2626", fontSize: 13 }}>
                &#9888; {calcErr}
              </div>
            )}
          </div>

          {/* Result */}
          {result && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
                <div style={{ background: "#2563eb", padding: "16px 20px", color: "#fff" }}>
                  <div style={{ fontSize: 13, opacity: 0.85 }}>Renewal Premium</div>
                  <div style={{ fontSize: 32, fontWeight: 700 }}>
                    {fmt(result.renewal_premium || result.gross_premium)}
                  </div>
                  <div style={{ fontSize: 12, opacity: 0.75, marginTop: 2 }}>
                    {result.premium_change_pct != null
                      ? (result.premium_change_pct > 0 ? "+" : "") + Number(result.premium_change_pct).toFixed(1) + "% vs last year"
                      : ""} | Valid 1 year
                  </div>
                </div>
                <div style={{ padding: 16 }}>
                  {[
                    ["Previous Premium", fmt(result.previous_premium)],
                    ["New NCB",          (result.new_ncb ?? newNCB) + "%"],
                    ["Recommendation",   result.recommendation || "APPROVE"],
                  ].map(([k, v], i) => (
                    <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0",
                      borderBottom: i < 2 ? "1px solid #f1f5f9" : "none", fontSize: 13 }}>
                      <span style={{ color: "#64748b" }}>{k}</span>
                      <span style={{ fontWeight: 600, color: k === "Recommendation"
                        ? (v === "APPROVE" ? "#16a34a" : v === "REJECT" ? "#dc2626" : "#f59e0b")
                        : "#0f172a" }}>{v}</span>
                    </div>
                  ))}
                  {result.risk_factors?.length > 0 && (
                    <div style={{ marginTop: 12, padding: "10px 12px", background: "#f8fafc", borderRadius: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Loading factors:</div>
                      {result.risk_factors.map((f, i) => (
                        <div key={i} style={{ fontSize: 11, color: "#64748b", marginBottom: 3 }}>• {f}</div>
                      ))}
                    </div>
                  )}

                  {/* Renew Policy button */}
                  {!renewed ? (
                    <div style={{ marginTop: 16 }}>
                      <button onClick={renewPolicy} disabled={renewLoading}
                        style={{ width: "100%", padding: "13px 0", borderRadius: 8, border: "none",
                          background: renewLoading ? "#94a3b8" : "#16a34a", color: "#fff",
                          fontWeight: 700, fontSize: 15, cursor: renewLoading ? "not-allowed" : "pointer" }}>
                        {renewLoading ? "Processing..." : "✅ Renew Policy"}
                      </button>
                      {renewErr && (
                        <div style={{ marginTop: 8, padding: "8px 12px", background: "#fef2f2",
                          border: "1px solid #fca5a5", borderRadius: 8, color: "#dc2626", fontSize: 12 }}>
                          ⚠ {renewErr}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ marginTop: 16, padding: "12px 16px", background: "#f0fdf4",
                      border: "1px solid #86efac", borderRadius: 10 }}>
                      <div style={{ fontWeight: 700, color: "#166534", marginBottom: 4 }}>
                        ✅ Policy Renewed Successfully!
                      </div>
                      <div style={{ fontSize: 13, color: "#166534" }}>
                        <strong>Renewal ID:</strong> {renewed.renewal_id}<br />
                        <strong>Valid:</strong> {renewed.start_date} → {renewed.end_date}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Risk Assessment — always shows with fallback */}
              <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
                <div style={{ padding: "14px 16px", borderBottom: "1px solid #f1f5f9" }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>AI Risk Assessment</span>
                  {result.explanation?.is_ml_shap === false && (
                    <span style={{ fontSize: 10, background: "#fef3c7", color: "#92400e", padding: "2px 7px",
                      borderRadius: 10, marginLeft: 8, fontWeight: 600 }}>Rule-based</span>
                  )}
                </div>
                <RiskGauge score={result.risk_score} />
                <ShapPanel explanation={result.explanation} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
