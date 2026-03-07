import { useState } from "react";
import insuranceAPI from "../services/api";

const safe = (e) => {
  if (!e) return "Unknown error";
  const d = e?.response?.data;
  if (d?.detail) return typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
  if (typeof e?.message === "string") return e.message;
  return String(e);
};

const fmt = (n) => `Rs. ${Number(n || 0).toLocaleString("en-LK", { maximumFractionDigits: 0 })}`;

const CLAIM_TYPES = [
  "Accidental Damage",
  "Theft of Vehicle",
  "Theft of Parts",
  "Third Party Liability",
  "Windscreen Damage",
  "Fire Damage",
  "Flood / Natural Disaster",
  "Own Damage",
];

const SEVERITIES = ["Minor", "Moderate", "Severe", "Total Loss"];

const PROVINCES = [
  "Western","Central","Southern","Northern","Eastern",
  "North Western","Uva","Sabaragamuwa","North Central",
];

const DEFAULT_FORM = {
  policy_number: "",
  claim_type: "Accidental Damage",
  accident_date: new Date().toISOString().slice(0, 10),
  accident_location: "",
  accident_description: "",
  accident_severity: "Minor",
  province: "Western",
  claim_amount_lkr: "",
  insured_value: "",
  driver_age: "",
  vehicle_age: "",
  third_party_involved: false,
  police_report_available: false,
  witness_available: false,
};

export default function Claims() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [errs, setErrs] = useState({});
  const [loading, setLoading] = useState(false);
  const [apiErr, setApiErr] = useState("");
  const [result, setResult] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  const set = (key, val) => {
    setForm(p => ({ ...p, [key]: val }));
    setErrs(p => ({ ...p, [key]: "" }));
  };

  const validate = () => {
    const e = {};
    if (!form.policy_number.trim()) e.policy_number = "Policy number is required";
    if (!form.accident_location.trim()) e.accident_location = "Accident location is required";
    if (!form.accident_description.trim() || form.accident_description.trim().length < 10)
      e.accident_description = "Please describe the accident (min 10 characters)";

    const iv = Number(form.insured_value);
    if (!form.insured_value || iv < 10000) e.insured_value = "Insured value must be at least Rs. 10,000";

    const ca = Number(form.claim_amount_lkr);
    if (!form.claim_amount_lkr || ca <= 0) e.claim_amount_lkr = "Claim amount is required";
    else if (ca < 1000) e.claim_amount_lkr = "Minimum claim amount is LKR 1,000";
    else if (iv && ca > iv) e.claim_amount_lkr = `Cannot exceed insured value (${fmt(iv)})`;

    const age = Number(form.driver_age);
    if (!form.driver_age || age < 18 || age > 80) e.driver_age = "Driver age must be 18–80";

    const va = Number(form.vehicle_age);
    if (!form.vehicle_age || va < 0 || va > 40) e.vehicle_age = "Vehicle age must be 0–40 years";

    return e;
  };

  const handleSubmit = async () => {
    const e = validate();
    if (Object.keys(e).length) { setErrs(e); return; }
    setErrs({});
    setLoading(true); setApiErr(""); setResult(null);
    try {
      const payload = {
        policy_number: form.policy_number.trim().toUpperCase(),
        claim_type: form.claim_type,
        accident_date: form.accident_date,
        accident_location: form.accident_location.trim(),
        accident_description: form.accident_description.trim(),
        accident_severity: form.accident_severity,
        province: form.province,
        claim_amount_lkr: Number(form.claim_amount_lkr),
        insured_value: Number(form.insured_value),
        driver_age: Number(form.driver_age),
        vehicle_age: Number(form.vehicle_age),
        third_party_involved: form.third_party_involved,
        police_report_available: form.police_report_available,
        witness_available: form.witness_available,
      };
      const res = await insuranceAPI.submitClaim(payload);
      setResult(res.data);
      setSubmitted(true);
    } catch (e) {
      setApiErr(safe(e));
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setForm(DEFAULT_FORM); setErrs({}); setResult(null);
    setSubmitted(false); setApiErr("");
  };

  // ── Success screen ──────────────────────────────────────────────────────────
  if (submitted && result) {
    const riskScore = result.risk_score;
    const riskLevel = riskScore < 25 ? "Low" : riskScore < 50 ? "Moderate" : riskScore < 70 ? "High" : "Very High";
    const riskColor = riskScore < 25 ? "#16a34a" : riskScore < 50 ? "#f59e0b" : riskScore < 70 ? "#ea580c" : "#dc2626";

    return (
      <div style={{ padding: 24, fontFamily: "'Segoe UI',sans-serif", background: "#f8fafc", minHeight: "100vh" }}>
        <div style={{ maxWidth: 700, margin: "0 auto" }}>
          <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 8px rgba(0,0,0,.08)" }}>
            <div style={{ background: "#16a34a", padding: "20px 24px", color: "#fff" }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>✅</div>
              <h2 style={{ margin: 0, fontSize: 20 }}>Claim Submitted Successfully</h2>
              <p style={{ margin: "4px 0 0", opacity: 0.85, fontSize: 13 }}>
                Reference: {result.claim_id || "CLM-" + Date.now()} · {new Date().toLocaleDateString("en-LK")}
              </p>
            </div>
            <div style={{ padding: 24 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
                {[
                  ["Policy", form.policy_number],
                  ["Claim Type", form.claim_type],
                  ["Claim Amount", fmt(form.claim_amount_lkr)],
                  ["Status", result.status || "Under Review"],
                  ["Severity", form.accident_severity],
                  ["Estimated Processing", result.processing_days ? `${result.processing_days} working days` : "7–14 working days"],
                ].map(([k, v]) => (
                  <div key={k} style={{ padding: "10px 14px", background: "#f8fafc", borderRadius: 8 }}>
                    <div style={{ fontSize: 11, color: "#64748b" }}>{k}</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", marginTop: 2 }}>{v}</div>
                  </div>
                ))}
              </div>

              {riskScore != null && (
                <div style={{ padding: 16, background: riskColor + "10", border: `1px solid ${riskColor}40`, borderRadius: 10, marginBottom: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>AI Risk Assessment</div>
                      <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                        {result.risk_note || "Based on driver profile and claim history"}
                      </div>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 32, fontWeight: 700, color: riskColor }}>{riskScore}</div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: riskColor }}>{riskLevel} Risk</div>
                    </div>
                  </div>
                </div>
              )}

              {result.recommendation && (
                <div style={{ padding: "12px 16px", background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8, fontSize: 13, color: "#92400e", marginBottom: 16 }}>
                  💡 {result.recommendation}
                </div>
              )}

              <button onClick={reset} style={{ padding: "10px 24px", borderRadius: 8, border: "none", background: "#2563eb", color: "#fff", fontWeight: 600, cursor: "pointer" }}>
                Submit Another Claim
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Form ────────────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: 24, fontFamily: "'Segoe UI',sans-serif", background: "#f8fafc", minHeight: "100vh" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f172a", margin: "0 0 4px" }}>📋 Submit a Claim</h1>
      <p style={{ color: "#64748b", marginTop: 0, marginBottom: 24 }}>All fields marked * are required. The AI will assess fraud risk automatically.</p>

      {apiErr && (
        <div style={{ padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, color: "#dc2626", marginBottom: 20, fontSize: 13 }}>
          ⚠ {apiErr}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* Section 1: Policy & Accident */}
        <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
          <h3 style={{ margin: "0 0 16px", fontSize: 14, fontWeight: 700 }}>📄 Policy & Accident Details</h3>

          <Field label="Policy Number *" error={errs.policy_number}>
            <input value={form.policy_number} onChange={e => set("policy_number", e.target.value.toUpperCase())}
              placeholder="e.g. NP00045355" style={inp(errs.policy_number)} />
          </Field>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="Claim Type *">
              <select value={form.claim_type} onChange={e => set("claim_type", e.target.value)} style={inp()}>
                {CLAIM_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Accident Severity *">
              <select value={form.accident_severity} onChange={e => set("accident_severity", e.target.value)} style={inp()}>
                {SEVERITIES.map(s => <option key={s}>{s}</option>)}
              </select>
            </Field>
          </div>

          <Field label="Accident Date *">
            <input type="date" value={form.accident_date} max={new Date().toISOString().slice(0, 10)}
              onChange={e => set("accident_date", e.target.value)} style={inp()} />
          </Field>

          <Field label="Province *">
            <select value={form.province} onChange={e => set("province", e.target.value)} style={inp()}>
              {PROVINCES.map(p => <option key={p}>{p}</option>)}
            </select>
          </Field>

          <Field label="Accident Location *" error={errs.accident_location}>
            <input value={form.accident_location} onChange={e => set("accident_location", e.target.value)}
              placeholder="e.g. Galle Road, Colombo 3" style={inp(errs.accident_location)} />
          </Field>

          <Field label="Description of Accident *" error={errs.accident_description}>
            <textarea value={form.accident_description} onChange={e => set("accident_description", e.target.value)}
              placeholder="Describe what happened in detail (min 10 characters)..."
              rows={4} style={{ ...inp(errs.accident_description), resize: "vertical" }} />
          </Field>
        </div>

        {/* Section 2: Financial & Driver */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 14, fontWeight: 700 }}>💰 Financial Details</h3>

            <Field label="Insured Value (LKR) *" error={errs.insured_value}>
              <input type="number" value={form.insured_value} onChange={e => set("insured_value", e.target.value)}
                placeholder="e.g. 5000000" style={inp(errs.insured_value)} />
            </Field>

            <Field label="Claim Amount (LKR) *" error={errs.claim_amount_lkr}>
              <input type="number" value={form.claim_amount_lkr} onChange={e => set("claim_amount_lkr", e.target.value)}
                placeholder="e.g. 250000" style={inp(errs.claim_amount_lkr)} />
              {form.claim_type === "Windscreen Damage" && (
                <p style={{ fontSize: 11, color: "#64748b", marginTop: 3 }}>Typical range: Rs. 15,000–120,000</p>
              )}
              {form.claim_type === "Theft of Vehicle" && (
                <p style={{ fontSize: 11, color: "#64748b", marginTop: 3 }}>Maximum = Sum Insured</p>
              )}
            </Field>
          </div>

          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 14, fontWeight: 700 }}>🚗 Driver & Vehicle</h3>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <Field label="Driver Age *" error={errs.driver_age}>
                <input type="number" value={form.driver_age} min={18} max={80}
                  onChange={e => set("driver_age", e.target.value)} placeholder="18–80" style={inp(errs.driver_age)} />
              </Field>
              <Field label="Vehicle Age (yrs) *" error={errs.vehicle_age}>
                <input type="number" value={form.vehicle_age} min={0} max={40}
                  onChange={e => set("vehicle_age", e.target.value)} placeholder="0–40" style={inp(errs.vehicle_age)} />
              </Field>
            </div>
          </div>

          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 14, fontWeight: 700 }}>📎 Supporting Evidence</h3>
            {[
              { key: "police_report_available", label: "Police report available", sub: "Required for theft and third-party claims" },
              { key: "third_party_involved", label: "Third party involved", sub: "Other vehicles or pedestrians affected" },
              { key: "witness_available", label: "Witness available", sub: "Independent witness present at accident" },
            ].map(item => (
              <label key={item.key} style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 12, cursor: "pointer" }}>
                <input type="checkbox" checked={form[item.key]} onChange={e => set(item.key, e.target.checked)}
                  style={{ marginTop: 2, accentColor: "#2563eb", width: 16, height: 16 }} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>{item.label}</div>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{item.sub}</div>
                </div>
              </label>
            ))}

            {form.claim_type === "Theft of Vehicle" && !form.police_report_available && (
              <div style={{ padding: "8px 12px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6, fontSize: 12, color: "#dc2626", marginTop: 8 }}>
                ⚠ Police report is required for Theft of Vehicle claims
              </div>
            )}
          </div>

          <button onClick={handleSubmit} disabled={loading}
            style={{ padding: "14px 28px", borderRadius: 10, border: "none",
              background: loading ? "#94a3b8" : "#2563eb", color: "#fff", fontWeight: 700, fontSize: 15,
              cursor: loading ? "not-allowed" : "pointer", width: "100%" }}>
            {loading ? "Processing…" : "📋 Submit Claim"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function Field({ label, error, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ fontSize: 13, fontWeight: 600, color: "#334155", display: "block", marginBottom: 5 }}>{label}</label>
      {children}
      {error && <p style={{ color: "#dc2626", fontSize: 11, marginTop: 4 }}>⚠ {error}</p>}
    </div>
  );
}

function inp(err) {
  return {
    width: "100%", boxSizing: "border-box",
    padding: "9px 12px", borderRadius: 8, fontSize: 13,
    border: `1px solid ${err ? "#dc2626" : "#e2e8f0"}`,
    outline: "none",
  };
}
