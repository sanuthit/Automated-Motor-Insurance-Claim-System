import { useState, useEffect, useRef } from "react";
import insuranceAPI from "../services/api";

// ── Helpers ───────────────────────────────────────────────────────────────────
const safe = (e) => {
  if (!e) return "Unknown error — check backend is running on port 8000";
  const d = e?.response?.data;
  if (d?.detail) return typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
  if (typeof e?.message === "string") return e.message;
  return String(e);
};
const fmt = (n) =>
  `Rs. ${Number(n || 0).toLocaleString("en-LK", { maximumFractionDigits: 0 })}`;

const CURRENT_YEAR = new Date().getFullYear();
const PROVINCES    = ["Western","Central","Southern","Northern","Eastern","North Western","Uva","Sabaragamuwa","North Central"];
const CONDITIONS   = ["Excellent","Good","Fair","Poor"];
const OCCUPATIONS  = ["Employed","Self-Employed","Business Owner","Government","Student","Retired","Unemployed","Driver/Transport"];
const GENDERS      = ["Male","Female"];                          // Other removed
const VEHICLE_TYPES_FALLBACK = ["Car","SUV","Van","Dual Purpose"]; // Motor Cycle removed

const DEFAULT_FORM = {
  customer_name:"", nic:"", gender:"Male", occupation:"Employed",
  driver_age:"", years_exp:"", province:"Western",
  vehicle_model:"", vehicle_year:"", engine_cc:"", vehicle_type:"Car",
  vehicle_condition:"Good", market_value:"", sum_insured:"",
  prev_ncb:0, is_existing_customer:false, is_blacklisted:false,
  images:false, inspection:false, fair_value:false,
  financial_interest:false, reg_book:false,
  valid_renewal_notice:false, rebate_approved:false,
};

// ── Sub-components ────────────────────────────────────────────────────────────
function Field({ label, error, hint, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ fontSize: 13, fontWeight: 600, color: "#334155", display: "block", marginBottom: 5 }}>{label}</label>
      {children}
      {error && <p style={{ color: "#dc2626", fontSize: 11, marginTop: 4 }}>⚠ {error}</p>}
      {hint && !error && <p style={{ color: "#94a3b8", fontSize: 11, marginTop: 3 }}>{hint}</p>}
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

// Autocomplete for vehicle model with DB lookup
function VehicleModelInput({ value, onChange, onTypeChange, vehicleTypes, error }) {
  const [models, setModels]   = useState([]);
  const [open, setOpen]       = useState(false);
  const [loading, setLoading] = useState(false);
  const modelMap = useRef({});
  const ref      = useRef(null);

  useEffect(() => {
    setLoading(true);
    insuranceAPI.getVehicleModels()
      .then(r => {
        const list = r?.data?.models || [];
        list.forEach(m => { modelMap.current[m.model] = m.vehicle_type; });
        setModels(list);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = value.trim().length > 0
    ? models.filter(m => m.model.toLowerCase().includes(value.toLowerCase())).slice(0, 10)
    : models.slice(0, 10);

  const select = (m) => {
    onChange(m.model);
    onTypeChange(m.vehicle_type);
    setOpen(false);
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <input
        value={value}
        onChange={e => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder={loading ? "Loading models…" : "e.g. Toyota Aqua"}
        style={inp(error)}
      />
      {open && filtered.length > 0 && (
        <div style={{
          position: "absolute", top: "100%", left: 0, right: 0, zIndex: 99,
          background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8,
          boxShadow: "0 4px 12px rgba(0,0,0,.12)", maxHeight: 220, overflowY: "auto",
        }}>
          {filtered.map(m => (
            <div key={m.model}
              onMouseDown={() => select(m)}
              style={{
                padding: "8px 12px", cursor: "pointer", fontSize: 13,
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}
              onMouseEnter={e => e.currentTarget.style.background = "#f1f5f9"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <span style={{ fontWeight: 500 }}>{m.model}</span>
              <span style={{ fontSize: 11, color: "#64748b", background: "#f8fafc", padding: "2px 6px", borderRadius: 4 }}>
                {m.vehicle_type}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ShapPanel({ explanation }) {
  if (!explanation?.available) return null;
  return (
    <div style={{ background: "#f8fafc", borderRadius: 10, padding: "14px 16px", marginTop: 12 }}>
      <div style={{ fontWeight: 700, fontSize: 13, color: "#0f172a", marginBottom: 10 }}>🧠 Risk Drivers</div>
      {explanation.top_drivers?.map((d, i) => {
        const isRisk = d.direction === "increases_risk";
        const bar = d.magnitude === "high" ? 70 : d.magnitude === "medium" ? 44 : 20;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 9 }}>
            <span style={{ color: isRisk ? "#dc2626" : "#16a34a", fontWeight: 700, width: 14 }}>
              {isRisk ? "▲" : "▼"}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                <span style={{ fontSize: 12, fontWeight: 500 }}>{d.feature}</span>
                <span style={{ fontSize: 11, color: isRisk ? "#dc2626" : "#16a34a" }}>{d.reason}</span>
              </div>
              <div style={{ height: 5, background: "#e2e8f0", borderRadius: 3 }}>
                <div style={{ height: 5, borderRadius: 3, width: `${bar}%`, background: isRisk ? "#dc2626" : "#16a34a" }} />
              </div>
            </div>
            <span style={{ fontSize: 11, fontFamily: "monospace", width: 48, textAlign: "right", color: isRisk ? "#dc2626" : "#16a34a" }}>
              {d.shap_value > 0 ? "+" : ""}{Number(d.shap_value).toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function NewPolicy() {
  const [step, setStep]     = useState(0);
  const [form, setForm]     = useState(DEFAULT_FORM);
  const [errs, setErrs]     = useState({});
  const [loading, setLoading]   = useState(false);
  const [issuing, setIssuing]   = useState(false);
  const [apiErr, setApiErr]     = useState("");
  const [result, setResult]     = useState(null);
  const [issued, setIssued]     = useState(null);   // {policy_id, start_date, end_date}
  const [siSuggested, setSiSuggested] = useState(null);
  const [vehicleTypes, setVehicleTypes] = useState(VEHICLE_TYPES_FALLBACK);

  // Load vehicle types from DB
  useEffect(() => {
    insuranceAPI.getVehicleTypes()
      .then(r => { if (r?.data?.types?.length) setVehicleTypes(r.data.types); })
      .catch(() => {});
  }, []);

  const set = (key, val) => {
    setForm(p => ({ ...p, [key]: val }));
    setErrs(p => ({ ...p, [key]: "" }));
  };

  // ── Validation Step 0 ────────────────────────────────────────────────────────
  const goNext = () => {
    const e = {};
    if (!form.customer_name.trim() || form.customer_name.trim().length < 2)
      e.customer_name = "Full name required (min 2 characters)";
    if (!form.nic.trim() || !/^(\d{9}[VvXx]|\d{12})$/.test(form.nic.trim()))
      e.nic = "Invalid NIC — use 901234567V or 199012345678";
    const age = Number(form.driver_age);
    if (!form.driver_age || age < 18 || age > 80)
      e.driver_age = "Age must be between 18 and 80";
    const exp = Number(form.years_exp);
    if (form.years_exp === "" || exp < 0)
      e.years_exp = "Experience cannot be negative";
    else if (exp > age - 16)
      e.years_exp = `Maximum ${age - 16} years for age ${age}`;
    if (Object.keys(e).length) { setErrs(e); return; }
    setErrs({}); setStep(1);
  };

  // ── Validation Step 1 ────────────────────────────────────────────────────────
  const validateStep1 = () => {
    const e = {};
    if (!form.vehicle_model.trim()) e.vehicle_model = "Vehicle model is required";
    const yr = Number(form.vehicle_year);
    if (!form.vehicle_year || yr < 1980 || yr > CURRENT_YEAR)
      e.vehicle_year = `Year must be 1980–${CURRENT_YEAR}`;
    const cc = Number(form.engine_cc);
    if (!form.engine_cc || cc < 50 || cc > 8000)
      e.engine_cc = "Engine CC must be 50–8000";
    const mv = Number(form.market_value);
    if (!form.market_value || mv < 100000)
      e.market_value = "Market value minimum: Rs. 100,000";
    const si = Number(form.sum_insured);
    if (!form.sum_insured || si < 100000)
      e.sum_insured = "Sum Insured minimum: Rs. 100,000";
    else if (mv && si > mv * 1.20)
      e.sum_insured = `Cannot exceed 120% of market value (${fmt(mv * 1.20)})`;
    if (Number(form.prev_ncb) > 0 && !form.valid_renewal_notice)
      e.valid_renewal_notice = "Renewal notice required when NCB > 0";
    return e;
  };

  const handleMarketValueChange = (val) => {
    set("market_value", val);
    const mv = Number(val);
    if (mv >= 100000) {
      const suggested = Math.round(mv * 0.95 / 1000) * 1000;
      setSiSuggested({ min: Math.round(mv * 0.80), suggested, max: Math.round(mv * 1.20) });
      if (!form.sum_insured) set("sum_insured", String(suggested));
    } else {
      setSiSuggested(null);
    }
  };

  // ── Calculate premium ────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    const e = validateStep1();
    if (Object.keys(e).length) { setErrs(e); return; }
    setErrs({}); setLoading(true); setApiErr(""); setResult(null); setIssued(null);
    try {
      const yr = Number(form.vehicle_year);
      const payload = {
        customer_name:        form.customer_name.trim(),
        nic:                  form.nic.trim().toUpperCase(),
        gender:               form.gender,
        occupation:           form.occupation,
        driver_age:           Number(form.driver_age),
        years_exp:            Number(form.years_exp),
        province:             form.province,
        vehicle_model:        form.vehicle_model.trim(),
        vehicle_year:         yr,
        vehicle_age:          Math.max(0, CURRENT_YEAR - yr),
        engine_cc:            Number(form.engine_cc),
        vehicle_type:         form.vehicle_type,
        vehicle_condition:    form.vehicle_condition,
        market_value:         Number(form.market_value),
        sum_insured:          Number(form.sum_insured),
        prev_ncb:             Number(form.prev_ncb),
        is_existing_customer: form.is_existing_customer ? "Yes" : "No",
        is_blacklisted:       form.is_blacklisted       ? "Yes" : "No",
        images:               form.images               ? "Yes" : "No",
        inspection:           form.inspection           ? "Yes" : "No",
        fair_value:           form.fair_value           ? "Yes" : "No",
        financial_interest:   form.financial_interest   ? "Yes" : "No",
        reg_book:             form.reg_book             ? "Yes" : "No",
        valid_renewal_notice: form.valid_renewal_notice ? "Yes" : "No",
        rebate_approved:      form.rebate_approved      ? "Yes" : "No",
      };
      const res = await insuranceAPI.predictPremium(payload);
      setResult(res.data);
      setStep(2);
    } catch (err) {
      setApiErr(safe(err));
    } finally {
      setLoading(false);
    }
  };

  // ── Issue policy → save to DB ────────────────────────────────────────────────
  const handleIssue = async () => {
    if (!result || issuing) return;
    setIssuing(true);
    try {
      const res = await insuranceAPI.issuePolicy({ ...form, ...result });
      setIssued(res.data);
    } catch (err) {
      setApiErr("Issue Policy error: " + safe(err));
    } finally {
      setIssuing(false);
    }
  };

  // ── Derived ───────────────────────────────────────────────────────────────────
  const riskScore = result?.risk_score;
  const riskLevel = riskScore == null ? null : riskScore < 25 ? "Low" : riskScore < 50 ? "Moderate" : riskScore < 70 ? "High" : "Very High";
  const riskColor = riskScore == null ? "#94a3b8" : riskScore < 25 ? "#16a34a" : riskScore < 50 ? "#f59e0b" : riskScore < 70 ? "#ea580c" : "#dc2626";

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: 24, fontFamily: "'Segoe UI',sans-serif", background: "#f8fafc", minHeight: "100vh" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f172a", margin: "0 0 4px" }}>✅ New Policy Registration</h1>
      <p style={{ color: "#64748b", marginTop: 0, marginBottom: 20 }}>
        AI-powered premium calculation · Sri Lanka rates (3%–5.5% of SI) · Vehicle models from database
      </p>

      {/* Step indicator */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        {["Customer Details", "Vehicle & Coverage", "Result"].map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%", display: "flex",
              alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13,
              background: step === i ? "#2563eb" : step > i ? "#16a34a" : "#e2e8f0",
              color: step >= i ? "#fff" : "#64748b",
            }}>
              {step > i ? "✓" : i + 1}
            </div>
            <span style={{ fontSize: 13, fontWeight: step === i ? 700 : 400, color: step === i ? "#2563eb" : "#64748b" }}>{s}</span>
            {i < 2 && <span style={{ color: "#cbd5e1" }}>›</span>}
          </div>
        ))}
      </div>

      {apiErr && (
        <div style={{ padding: "12px 16px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, color: "#dc2626", marginBottom: 20, fontSize: 13 }}>
          ⚠ {apiErr}
        </div>
      )}

      {/* ── STEP 0 — Customer ── */}
      {step === 0 && (
        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,.06)", maxWidth: 720 }}>
          <h3 style={{ margin: "0 0 20px", fontSize: 15, fontWeight: 700 }}>Customer Information</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <Field label="Full Name *" error={errs.customer_name}>
              <input value={form.customer_name} onChange={e => set("customer_name", e.target.value)} placeholder="Enter full name" style={inp(errs.customer_name)} />
            </Field>
            <Field label="NIC Number *" error={errs.nic}>
              <input value={form.nic} onChange={e => set("nic", e.target.value.toUpperCase())} placeholder="901234567V or 199012345678" style={inp(errs.nic)} />
            </Field>
            <Field label="Gender">
              <select value={form.gender} onChange={e => set("gender", e.target.value)} style={inp()}>
                {GENDERS.map(g => <option key={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Occupation">
              <select value={form.occupation} onChange={e => set("occupation", e.target.value)} style={inp()}>
                {OCCUPATIONS.map(o => <option key={o}>{o}</option>)}
              </select>
            </Field>
            <Field label="Driver Age *" error={errs.driver_age}>
              <input type="number" min={18} max={80} value={form.driver_age} onChange={e => set("driver_age", e.target.value)} placeholder="18–80" style={inp(errs.driver_age)} />
            </Field>
            <Field label="Years of Driving Experience *" error={errs.years_exp}>
              <input type="number" min={0} value={form.years_exp} onChange={e => set("years_exp", e.target.value)} placeholder="0+" style={inp(errs.years_exp)} />
            </Field>
            <Field label="Province">
              <select value={form.province} onChange={e => set("province", e.target.value)} style={inp()}>
                {PROVINCES.map(p => <option key={p}>{p}</option>)}
              </select>
            </Field>
            <Field label="Previous NCB (%)">
              <select value={form.prev_ncb} onChange={e => set("prev_ncb", Number(e.target.value))} style={inp()}>
                {[0, 10, 20, 30, 40, 50].map(v => <option key={v} value={v}>{v}%</option>)}
              </select>
            </Field>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, marginTop: 8 }}>
            <input type="checkbox" checked={form.is_existing_customer} onChange={e => set("is_existing_customer", e.target.checked)} style={{ accentColor: "#2563eb", width: 16, height: 16 }} />
            <span style={{ fontWeight: 600, color: "#334155" }}>Existing customer</span>
          </label>
          <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end" }}>
            <button onClick={goNext} style={{ padding: "11px 28px", borderRadius: 8, border: "none", background: "#2563eb", color: "#fff", fontWeight: 700, fontSize: 14, cursor: "pointer" }}>
              Next: Vehicle Info ›
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 1 — Vehicle ── */}
      {step === 1 && (
        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,.06)", maxWidth: 800 }}>
          <h3 style={{ margin: "0 0 20px", fontSize: 15, fontWeight: 700 }}>Vehicle & Coverage</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            <Field label="Vehicle Model *" error={errs.vehicle_model}>
              <VehicleModelInput
                value={form.vehicle_model}
                onChange={v => set("vehicle_model", v)}
                onTypeChange={t => set("vehicle_type", t)}
                vehicleTypes={vehicleTypes}
                error={errs.vehicle_model}
              />
            </Field>
            <Field label="Vehicle Year *" error={errs.vehicle_year}>
              <input type="number" min={1980} max={CURRENT_YEAR} value={form.vehicle_year} onChange={e => set("vehicle_year", e.target.value)} placeholder={`1980–${CURRENT_YEAR}`} style={inp(errs.vehicle_year)} />
            </Field>
            <Field label="Engine CC *" error={errs.engine_cc}>
              <input type="number" min={50} max={8000} value={form.engine_cc} onChange={e => set("engine_cc", e.target.value)} placeholder="e.g. 1500" style={inp(errs.engine_cc)} />
            </Field>
            <Field label="Vehicle Type">
              <select value={form.vehicle_type} onChange={e => set("vehicle_type", e.target.value)} style={inp()}>
                {vehicleTypes.map(t => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Vehicle Condition">
              <select value={form.vehicle_condition} onChange={e => set("vehicle_condition", e.target.value)} style={inp()}>
                {CONDITIONS.map(c => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <div />
            <Field label="Current Market Value (LKR) *" error={errs.market_value}>
              <input type="number" value={form.market_value} onChange={e => handleMarketValueChange(e.target.value)} placeholder="Min Rs. 100,000" style={inp(errs.market_value)} />
            </Field>
            <Field label="Sum Insured (LKR) *" error={errs.sum_insured}
              hint={siSuggested ? `Suggested: ${fmt(siSuggested.suggested)} · Range: ${fmt(siSuggested.min)}–${fmt(siSuggested.max)}` : ""}>
              <input type="number" value={form.sum_insured} onChange={e => set("sum_insured", e.target.value)} placeholder="Min Rs. 100,000" style={inp(errs.sum_insured)} />
              {siSuggested && (
                <button type="button" onClick={() => set("sum_insured", String(siSuggested.suggested))}
                  style={{ marginTop: 4, padding: "3px 10px", borderRadius: 6, border: "none", background: "#eff6ff", color: "#2563eb", fontSize: 11, cursor: "pointer", fontWeight: 600 }}>
                  Use suggested {fmt(siSuggested.suggested)}
                </button>
              )}
            </Field>
          </div>

          <div style={{ marginTop: 16 }}>
            <h4 style={{ fontSize: 13, fontWeight: 700, color: "#334155", marginBottom: 10 }}>Document Compliance</h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[
                { key: "images",               label: "Vehicle images provided" },
                { key: "inspection",           label: "Inspection report submitted" },
                { key: "fair_value",           label: "Fair value report attached" },
                { key: "reg_book",             label: "Registration book verified" },
                { key: "financial_interest",   label: "Financial interest declared" },
                { key: "valid_renewal_notice", label: "Valid renewal notice (if NCB > 0)", err: errs.valid_renewal_notice },
                { key: "rebate_approved",      label: "Rebate approved by underwriter" },
              ].map(item => (
                <div key={item.key}>
                  <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                    <input type="checkbox" checked={form[item.key]} onChange={e => set(item.key, e.target.checked)} style={{ accentColor: "#2563eb", width: 15, height: 15 }} />
                    <span style={{ fontSize: 13, color: "#334155" }}>{item.label}</span>
                  </label>
                  {item.err && <p style={{ color: "#dc2626", fontSize: 11, margin: "2px 0 0 23px" }}>⚠ {item.err}</p>}
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 20, display: "flex", gap: 10, justifyContent: "space-between" }}>
            <button onClick={() => setStep(0)} style={{ padding: "11px 24px", borderRadius: 8, border: "1px solid #e2e8f0", background: "#fff", color: "#334155", fontWeight: 600, cursor: "pointer", fontSize: 14 }}>
              ‹ Back
            </button>
            <button onClick={handleSubmit} disabled={loading} style={{ padding: "11px 28px", borderRadius: 8, border: "none", background: loading ? "#94a3b8" : "#2563eb", color: "#fff", fontWeight: 700, fontSize: 14, cursor: loading ? "not-allowed" : "pointer" }}>
              {loading ? "Calculating…" : "⚡ Calculate Premium"}
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 2 — Result ── */}
      {step === 2 && result && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, maxWidth: 900 }}>

          {/* Premium card */}
          <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 1px 8px rgba(0,0,0,.08)" }}>
            <div style={{ background: "#2563eb", padding: "20px 24px", color: "#fff" }}>
              <div style={{ fontSize: 13, opacity: 0.85 }}>Annual Premium</div>
              <div style={{ fontSize: 36, fontWeight: 700 }}>{fmt(result.gross_premium)}</div>
              <div style={{ fontSize: 12, opacity: 0.75, marginTop: 2 }}>
                {result.rate_pct ? `Rate: ${(result.rate_pct * 100).toFixed(2)}% of SI` : ""} · Comprehensive
              </div>
            </div>
            <div style={{ padding: "16px 20px" }}>
              {[
                ["Base Premium",    fmt(result.base_premium)],
                ["NCB Discount",    `– ${fmt(result.ncb_discount)}`],
                ["Net Premium",     fmt(result.net_premium)],
                ["Stamp Duty (1%)", fmt(result.stamp_duty)],
                ["VAT (8%)",        fmt(result.vat)],
                ["CESS (0.5%)",     fmt(result.cess)],
                ["Gross Total",     fmt(result.gross_premium)],
              ].map(([k, v], i) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0",
                  borderBottom: i < 6 ? "1px solid #f1f5f9" : "none",
                  fontWeight: i === 6 ? 700 : 400, fontSize: 13,
                  color: i === 6 ? "#0f172a" : v.startsWith("–") ? "#16a34a" : "#334155" }}>
                  <span>{k}</span><span>{v}</span>
                </div>
              ))}
              <div style={{ marginTop: 16, padding: "10px 14px", background: "#f8fafc", borderRadius: 8, fontSize: 11, color: "#64748b" }}>
                Premium period: Today – {new Date(Date.now() + 365 * 86400000).toLocaleDateString("en-LK")}
              </div>
            </div>
          </div>

          {/* Risk card */}
          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 8px rgba(0,0,0,.08)" }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>AI Risk Assessment</h3>
            {riskScore != null && (
              <div style={{ textAlign: "center", marginBottom: 12 }}>
                <svg width={140} height={140} viewBox="0 0 140 140">
                  <circle cx={70} cy={70} r={55} fill="none" stroke="#f1f5f9" strokeWidth={13} />
                  <circle cx={70} cy={70} r={55} fill="none" stroke={riskColor} strokeWidth={13}
                    strokeDasharray={`${(riskScore / 100) * 346} 346`}
                    strokeLinecap="round" transform="rotate(-90 70 70)" />
                  <text x={70} y={66} textAnchor="middle" fontSize={28} fontWeight={700} fill={riskColor}>{riskScore}</text>
                  <text x={70} y={84} textAnchor="middle" fontSize={11} fill="#64748b">{riskLevel} Risk</text>
                </svg>
              </div>
            )}
            <ShapPanel explanation={result.explanation} />

            <div style={{ marginTop: 12 }}>
              {[["Customer", form.customer_name], ["Vehicle", `${form.vehicle_model} (${form.vehicle_year})`],
                ["Sum Insured", fmt(form.sum_insured)], ["Market Value", fmt(form.market_value)], ["Province", form.province]
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 12 }}>
                  <span style={{ color: "#64748b" }}>{k}</span>
                  <span style={{ fontWeight: 600, color: "#0f172a" }}>{v}</span>
                </div>
              ))}
            </div>

            {/* Issue / New policy buttons */}
            {!issued ? (
              <div style={{ marginTop: 16, display: "flex", gap: 10 }}>
                <button onClick={handleIssue} disabled={issuing}
                  style={{ flex: 1, padding: "11px 0", borderRadius: 8, border: "none",
                    background: issuing ? "#94a3b8" : "#16a34a", color: "#fff", fontWeight: 700,
                    cursor: issuing ? "not-allowed" : "pointer", fontSize: 14 }}>
                  {issuing ? "Issuing…" : "✓ Issue Policy"}
                </button>
                <button onClick={() => { setStep(0); setForm(DEFAULT_FORM); setResult(null); setErrs({}); setSiSuggested(null); setIssued(null); setApiErr(""); }}
                  style={{ flex: 1, padding: "11px 0", borderRadius: 8, border: "1px solid #e2e8f0", background: "#fff", color: "#334155", fontWeight: 600, cursor: "pointer", fontSize: 14 }}>
                  New Policy
                </button>
              </div>
            ) : (
              <div style={{ marginTop: 16, padding: "14px 16px", background: "#f0fdf4", borderRadius: 10, border: "1px solid #bbf7d0" }}>
                <div style={{ fontWeight: 700, color: "#15803d", fontSize: 14, marginBottom: 6 }}>✅ Policy Issued Successfully!</div>
                <div style={{ fontSize: 13, color: "#166534" }}>
                  <strong>Policy ID:</strong> {issued.policy_id}<br />
                  <strong>Valid:</strong> {issued.start_date} → {issued.end_date}
                </div>
                <button onClick={() => { setStep(0); setForm(DEFAULT_FORM); setResult(null); setErrs({}); setSiSuggested(null); setIssued(null); setApiErr(""); }}
                  style={{ marginTop: 10, padding: "8px 20px", borderRadius: 8, border: "none", background: "#16a34a", color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 13 }}>
                  + Register Another Policy
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
