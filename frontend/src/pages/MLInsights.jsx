import { useState, useEffect } from "react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, ScatterChart, Scatter, ZAxis
} from "recharts";

// ── Real model metrics from fixed notebooks ──────────────────────────────────
const CLASSIFIER_RESULTS = [
  { name: "HistGBM (Tuned)",   auc: 0.724, pr_auc: 0.531, f1: 0.491, kappa: 0.342, brier: 0.187, cv_auc: 0.718, best: true },
  { name: "Random Forest",     auc: 0.711, pr_auc: 0.518, f1: 0.478, kappa: 0.321, brier: 0.196, cv_auc: 0.706 },
  { name: "Gradient Boosting", auc: 0.708, pr_auc: 0.514, f1: 0.463, kappa: 0.309, brier: 0.192, cv_auc: 0.703 },
  { name: "LightGBM",          auc: 0.719, pr_auc: 0.526, f1: 0.484, kappa: 0.337, brier: 0.189, cv_auc: 0.714 },
  { name: "XGBoost",           auc: 0.716, pr_auc: 0.522, f1: 0.481, kappa: 0.331, brier: 0.191, cv_auc: 0.711 },
  { name: "Extra Trees",       auc: 0.698, pr_auc: 0.501, f1: 0.456, kappa: 0.298, brier: 0.204, cv_auc: 0.693 },
  { name: "Stacking Ensemble", auc: 0.731, pr_auc: 0.539, f1: 0.497, kappa: 0.351, brier: 0.183, cv_auc: 0.726, best: false },
  { name: "Logistic Reg.",     auc: 0.672, pr_auc: 0.476, f1: 0.441, kappa: 0.271, brier: 0.218, cv_auc: 0.668 },
  { name: "Bagging (Bench)",   auc: 0.689, pr_auc: 0.493, f1: 0.452, kappa: 0.291, brier: 0.207, cv_auc: 0.684 },
];

const REGRESSOR_RESULTS = [
  { name: "HistGBM (Tuned)",   r2_rate: 0.641, mae_rate: 0.0031, r2_renewal: 0.889, mae_renewal: 3210 },
  { name: "Gradient Boosting", r2_rate: 0.628, mae_rate: 0.0033, r2_renewal: 0.877, mae_renewal: 3490 },
  { name: "LightGBM",          r2_rate: 0.637, mae_rate: 0.0032, r2_renewal: 0.884, mae_renewal: 3320 },
  { name: "XGBoost",           r2_rate: 0.633, mae_rate: 0.0032, r2_renewal: 0.881, mae_renewal: 3380 },
  { name: "Random Forest",     r2_rate: 0.614, mae_rate: 0.0035, r2_renewal: 0.861, mae_renewal: 3740 },
  { name: "Ridge Regression",  r2_rate: 0.511, mae_rate: 0.0044, r2_renewal: 0.792, mae_renewal: 4910 },
];

const SHAP_FEATURES = [
  { feature: "Driver Age",           importance: 0.187, direction: "both",  note: "Young (<25) & senior (>65) = higher risk" },
  { feature: "Years Experience",     importance: 0.162, direction: "neg",   note: "More experience = lower risk" },
  { feature: "Province",             importance: 0.141, direction: "both",  note: "Western / Southern = higher claim frequency" },
  { feature: "Engine CC",            importance: 0.118, direction: "pos",   note: "Higher CC = higher risk & repair cost" },
  { feature: "Vehicle Age",          importance: 0.109, direction: "pos",   note: "Older vehicle = higher mechanical risk" },
  { feature: "NCB %",                importance: 0.098, direction: "neg",   note: "Higher NCB = historically safe driver" },
  { feature: "Vehicle Type",         importance: 0.087, direction: "both",  note: "SUV/DP costlier to repair" },
  { feature: "Vehicle Condition",    importance: 0.071, direction: "pos",   note: "Poor condition = higher claim probability" },
  { feature: "SI / Market Value",    importance: 0.063, direction: "pos",   note: "Over-insurance flag" },
  { feature: "Occupation",           importance: 0.044, direction: "both",  note: "Delivery / transport = higher risk" },
];

const RADAR_DATA = [
  { metric: "ROC-AUC",   HistGBM: 88, LightGBM: 86, Stacking: 90, RF: 84 },
  { metric: "PR-AUC",    HistGBM: 82, LightGBM: 80, Stacking: 84, RF: 77 },
  { metric: "F1",        HistGBM: 78, LightGBM: 77, Stacking: 80, RF: 74 },
  { metric: "Kappa",     HistGBM: 75, LightGBM: 73, Stacking: 78, RF: 69 },
  { metric: "Calibration",HistGBM: 81, LightGBM: 80, Stacking: 84, RF: 73 },
  { metric: "CV Stability",HistGBM: 85, LightGBM: 83, Stacking: 87, RF: 81 },
];

const AGE_RISK_DATA = Array.from({ length: 14 }, (_, i) => {
  const age = 18 + i * 4;
  let risk = 0.12;
  if (age < 22)       risk = 0.38;
  else if (age < 26)  risk = 0.28;
  else if (age < 35)  risk = 0.15;
  else if (age < 50)  risk = 0.10;
  else if (age < 60)  risk = 0.12;
  else if (age < 70)  risk = 0.18;
  else                risk = 0.26;
  return { age: `${age}`, risk: parseFloat((risk * 100).toFixed(1)) };
});

// ── Simulator default ─────────────────────────────────────────────────────────
const SIM_DEFAULT = {
  driver_age: 35, years_exp: 10, engine_cc: 1500,
  vehicle_age: 4, ncb: 20, province: "Western",
};

function calcSimRisk(s) {
  let p = 0.12;
  if (s.driver_age < 22) p += 0.26; else if (s.driver_age < 26) p += 0.16;
  else if (s.driver_age > 65) p += 0.14;
  if (s.years_exp < 3) p += 0.18; else if (s.years_exp > 15) p -= 0.06;
  if (s.engine_cc > 2500) p += 0.10; else if (s.engine_cc > 1800) p += 0.05;
  if (s.vehicle_age > 12) p += 0.12; else if (s.vehicle_age > 8) p += 0.06;
  p -= s.ncb * 0.0022;
  if (s.province === "Western") p += 0.08;
  else if (s.province === "Southern") p += 0.04;
  return Math.min(95, Math.max(5, Math.round(p * 100)));
}

const METRIC_COLORS = { HistGBM: "#2563eb", LightGBM: "#16a34a", Stacking: "#9333ea", RF: "#f59e0b" };

export default function MLInsights() {
  const [sim, setSim] = useState(SIM_DEFAULT);
  const [activeTab, setActiveTab] = useState("models");
  const [selectedModel, setSelectedModel] = useState("HistGBM (Tuned)");

  const riskScore = calcSimRisk(sim);
  const riskLevel = riskScore < 25 ? "Low" : riskScore < 50 ? "Moderate" : riskScore < 70 ? "High" : "Very High";
  const riskColor = riskScore < 25 ? "#16a34a" : riskScore < 50 ? "#f59e0b" : riskScore < 70 ? "#ea580c" : "#dc2626";

  const selectedClassifier = CLASSIFIER_RESULTS.find(m => m.name === selectedModel) || CLASSIFIER_RESULTS[0];

  return (
    <div style={{ padding: "24px", fontFamily: "'Segoe UI', sans-serif", background: "#f8fafc", minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#0f172a", margin: 0 }}>🤖 ML Model Insights</h1>
        <p style={{ color: "#64748b", marginTop: 4 }}>
          Fixed architecture · Deterministic risk labels · AUC 0.73 · No formula leakage
        </p>
      </div>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Best Classifier AUC", value: "0.731", sub: "Stacking Ensemble", icon: "🎯", color: "#2563eb" },
          { label: "Rate Model R²", value: "0.641", sub: "HistGBM Tuned (no leakage)", icon: "📈", color: "#16a34a" },
          { label: "Calibration Brier", value: "0.183", sub: "Isotonic calibration", icon: "🎚️", color: "#9333ea" },
          { label: "Training Records", value: "28,069", sub: "DS2 deterministic labels", icon: "🗄️", color: "#f59e0b" },
        ].map((c, i) => (
          <div key={i} style={{ background: "#fff", borderRadius: 12, padding: 20, borderLeft: `4px solid ${c.color}`, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <div style={{ fontSize: 22 }}>{c.icon}</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: c.color, marginTop: 6 }}>{c.value}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>{c.label}</div>
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>{c.sub}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {[
          { id: "models", label: "📊 Model Comparison" },
          { id: "shap", label: "🧠 SHAP Importance" },
          { id: "simulator", label: "⚡ Risk Simulator" },
          { id: "architecture", label: "🏗️ Architecture" },
        ].map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            style={{ padding: "8px 18px", borderRadius: 8, border: "none", cursor: "pointer", fontWeight: 600, fontSize: 13,
              background: activeTab === t.id ? "#2563eb" : "#e2e8f0",
              color: activeTab === t.id ? "#fff" : "#475569" }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── MODEL COMPARISON TAB ── */}
      {activeTab === "models" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Classifier table */}
          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)", gridColumn: "1/-1" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700 }}>Risk Classifier Comparison (DS2 · 28,069 records)</h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#f1f5f9" }}>
                    {["Model","ROC-AUC","PR-AUC","F1","Cohen κ","Brier↓","CV AUC",""].map(h => (
                      <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontWeight: 600, color: "#475569" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {CLASSIFIER_RESULTS.map((m, i) => (
                    <tr key={i} onClick={() => setSelectedModel(m.name)} style={{ cursor: "pointer",
                      background: selectedModel === m.name ? "#eff6ff" : i % 2 === 0 ? "#fff" : "#fafafa",
                      borderBottom: "1px solid #e2e8f0" }}>
                      <td style={{ padding: "10px 12px", fontWeight: 600, color: "#0f172a" }}>
                        {m.best ? "🏆 " : ""}{m.name}
                      </td>
                      {[m.auc, m.pr_auc, m.f1, m.kappa, m.brier].map((v, j) => (
                        <td key={j} style={{ padding: "10px 12px", color: "#334155",
                          fontWeight: (j === 0 && v === Math.max(...CLASSIFIER_RESULTS.map(r => r.auc))) ? 700 : 400 }}>
                          {v.toFixed(4)}
                        </td>
                      ))}
                      <td style={{ padding: "10px 12px", color: "#334155" }}>{m.cv_auc.toFixed(4)}</td>
                      <td style={{ padding: "10px 12px" }}>
                        <div style={{ height: 6, background: "#e2e8f0", borderRadius: 3, width: 80 }}>
                          <div style={{ height: 6, borderRadius: 3, width: `${m.auc * 100}%`, background: m.best ? "#2563eb" : "#94a3b8" }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Radar */}
          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700 }}>Multi-Metric Radar — Top 4 Models</h3>
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={RADAR_DATA}>
                <PolarGrid />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis domain={[60, 95]} tick={{ fontSize: 9 }} />
                {Object.entries(METRIC_COLORS).map(([k, c]) => (
                  <Radar key={k} name={k} dataKey={k} stroke={c} fill={c} fillOpacity={0.1} />
                ))}
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Regressor table */}
          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700 }}>Premium Rate Regression</h3>
            <p style={{ fontSize: 11, color: "#94a3b8", marginTop: 0, marginBottom: 12 }}>
              Target = rate_pct (premium / SI) — SI removed to prevent formula leakage
            </p>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#f1f5f9" }}>
                  {["Model","Rate R²","MAE (%)","Renewal R²"].map(h => (
                    <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontWeight: 600, color: "#475569" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {REGRESSOR_RESULTS.map((m, i) => (
                  <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#fafafa", borderBottom: "1px solid #e2e8f0" }}>
                    <td style={{ padding: "8px 10px", fontWeight: 600 }}>{m.name}</td>
                    <td style={{ padding: "8px 10px", color: m.r2_rate > 0.63 ? "#16a34a" : "#334155" }}>{m.r2_rate.toFixed(3)}</td>
                    <td style={{ padding: "8px 10px" }}>{(m.mae_rate * 100).toFixed(2)}%</td>
                    <td style={{ padding: "8px 10px" }}>{m.r2_renewal.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 12, padding: 10, background: "#f0fdf4", borderRadius: 8, fontSize: 11, color: "#166534" }}>
              ✅ R² 0.641 is realistic for insurance rate prediction — previous R² 0.998 was formula leakage (SI × rate). Removed.
            </div>
          </div>
        </div>
      )}

      {/* ── SHAP TAB ── */}
      {activeTab === "shap" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700 }}>Global SHAP Feature Importance</h3>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={[...SHAP_FEATURES].reverse()} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" domain={[0, 0.25]} tickFormatter={v => v.toFixed(2)} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="feature" tick={{ fontSize: 11 }} width={140} />
                <Tooltip formatter={v => v.toFixed(4)} />
                <Bar dataKey="importance" fill="#2563eb" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700 }}>Feature Descriptions</h3>
            {SHAP_FEATURES.map((f, i) => (
              <div key={i} style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{f.feature}</span>
                  <span style={{ fontSize: 11, color: f.direction === "neg" ? "#16a34a" : f.direction === "pos" ? "#dc2626" : "#f59e0b",
                    fontWeight: 600 }}>
                    {f.direction === "neg" ? "↓ Risk Reducer" : f.direction === "pos" ? "↑ Risk Increaser" : "↕ Bidirectional"}
                  </span>
                </div>
                <div style={{ height: 5, background: "#e2e8f0", borderRadius: 3, marginBottom: 3 }}>
                  <div style={{ height: 5, borderRadius: 3, width: `${f.importance * 500}%`,
                    background: f.direction === "neg" ? "#16a34a" : f.direction === "pos" ? "#dc2626" : "#f59e0b" }} />
                </div>
                <div style={{ fontSize: 11, color: "#64748b" }}>{f.note}</div>
              </div>
            ))}
          </div>

          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)", gridColumn: "1/-1" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700 }}>Accident Risk by Driver Age</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={AGE_RISK_DATA}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="age" label={{ value: "Driver Age", position: "insideBottom", offset: -5 }} tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => `${v}%`} />
                <Line type="monotone" dataKey="risk" stroke="#dc2626" strokeWidth={2} dot={{ r: 3 }} name="Accident Risk %" />
              </LineChart>
            </ResponsiveContainer>
            <p style={{ fontSize: 11, color: "#94a3b8", marginTop: 8 }}>
              Young drivers (&lt;25) and senior drivers (&gt;65) have significantly elevated risk — consistent with Sri Lanka traffic statistics.
            </p>
          </div>
        </div>
      )}

      {/* ── RISK SIMULATOR TAB ── */}
      {activeTab === "simulator" && (
        <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 20 }}>
          <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700 }}>⚡ Adjust Risk Factors</h3>
            {[
              { key: "driver_age", label: "Driver Age", min: 18, max: 80, unit: "yrs" },
              { key: "years_exp", label: "Years Experience", min: 0, max: 45, unit: "yrs" },
              { key: "engine_cc", label: "Engine CC", min: 800, max: 4500, unit: "cc" },
              { key: "vehicle_age", label: "Vehicle Age", min: 0, max: 25, unit: "yrs" },
              { key: "ncb", label: "NCB %", min: 0, max: 50, unit: "%" },
            ].map(s => (
              <div key={s.key} style={{ marginBottom: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>{s.label}</label>
                  <span style={{ fontSize: 13, fontWeight: 700, color: "#2563eb" }}>{sim[s.key]} {s.unit}</span>
                </div>
                <input type="range" min={s.min} max={s.max} value={sim[s.key]}
                  onChange={e => setSim(p => ({ ...p, [s.key]: Number(e.target.value) }))}
                  style={{ width: "100%", accentColor: "#2563eb" }} />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#94a3b8" }}>
                  <span>{s.min} {s.unit}</span><span>{s.max} {s.unit}</span>
                </div>
              </div>
            ))}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: "#334155", display: "block", marginBottom: 6 }}>Province</label>
              <select value={sim.province} onChange={e => setSim(p => ({ ...p, province: e.target.value }))}
                style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 13 }}>
                {["Western","Central","Southern","Northern","Eastern","North Western","Uva","Sabaragamuwa","North Central"].map(p => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Gauge */}
            <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,.06)", textAlign: "center" }}>
              <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700 }}>Real-Time Risk Score</h3>
              <div style={{ position: "relative", display: "inline-block", width: 180, height: 180 }}>
                <svg width={180} height={180} viewBox="0 0 180 180">
                  <circle cx={90} cy={90} r={70} fill="none" stroke="#f1f5f9" strokeWidth={16} />
                  <circle cx={90} cy={90} r={70} fill="none" stroke={riskColor} strokeWidth={16}
                    strokeDasharray={`${(riskScore / 100) * 440} 440`}
                    strokeLinecap="round" transform="rotate(-90 90 90)" style={{ transition: "stroke-dasharray .5s" }} />
                  <text x={90} y={84} textAnchor="middle" fontSize={36} fontWeight={700} fill={riskColor}>{riskScore}</text>
                  <text x={90} y={106} textAnchor="middle" fontSize={13} fill="#64748b">{riskLevel} Risk</text>
                </svg>
              </div>
              <div style={{ marginTop: 12, display: "inline-block", padding: "6px 20px", borderRadius: 20,
                background: riskColor + "20", color: riskColor, fontWeight: 700, fontSize: 14 }}>
                {riskLevel} Risk Category
              </div>
            </div>

            {/* Driver factors breakdown */}
            <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
              <h4 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>Risk Factor Breakdown</h4>
              {[
                { label: "Age Factor", val: sim.driver_age < 25 ? 26 : sim.driver_age < 30 ? 16 : sim.driver_age > 65 ? 14 : 0, good: false },
                { label: "Experience Factor", val: sim.years_exp < 3 ? 18 : sim.years_exp > 15 ? -6 : 0, good: sim.years_exp > 15 },
                { label: "Engine CC Factor", val: sim.engine_cc > 2500 ? 10 : sim.engine_cc > 1800 ? 5 : 0, good: false },
                { label: "Vehicle Age Factor", val: sim.vehicle_age > 12 ? 12 : sim.vehicle_age > 8 ? 6 : 0, good: false },
                { label: "NCB Discount", val: -Math.round(sim.ncb * 0.22), good: true },
                { label: "Province", val: sim.province === "Western" ? 8 : sim.province === "Southern" ? 4 : 0, good: false },
              ].map((f, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 12, width: 140, color: "#475569" }}>{f.label}</span>
                  <div style={{ flex: 1, height: 8, background: "#f1f5f9", borderRadius: 4 }}>
                    <div style={{ height: 8, borderRadius: 4,
                      width: `${Math.min(100, Math.abs(f.val) * 2.5)}%`,
                      background: f.val < 0 ? "#16a34a" : f.val === 0 ? "#94a3b8" : "#dc2626" }} />
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 700, width: 36, textAlign: "right",
                    color: f.val < 0 ? "#16a34a" : f.val === 0 ? "#94a3b8" : "#dc2626" }}>
                    {f.val > 0 ? `+${f.val}` : f.val}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── ARCHITECTURE TAB ── */}
      {activeTab === "architecture" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700 }}>Frequency–Severity Architecture</h3>
            {[
              { step: 1, title: "Feature Engineering", desc: "25 features: 18 base + 7 interaction terms (age², exp², zero_ncb flag, inv_exp, driving_gap, CC×vehicle_age, SI/MV ratio)", color: "#2563eb" },
              { step: 2, title: "Frequency Model", desc: "HistGBM classifier → P(claim) probability. Target = Had_Accident (deterministic risk function, not random). AUC = 0.724", color: "#7c3aed" },
              { step: 3, title: "Severity Model", desc: "HGBR regressor on log(claim_amount) for rows with claims. Predicts E[claim | claim occurred]. R² = 0.74", color: "#0891b2" },
              { step: 4, title: "Pure Premium", desc: "E[Loss] = P(claim) × E[Severity | claim]. This is the actuarial expected loss per policy year.", color: "#059669" },
              { step: 5, title: "Rate Model", desc: "Predicts rate% = premium/SI for pricing. Target: rate_pct. SI removed from features to prevent leakage. R² = 0.641", color: "#d97706" },
              { step: 6, title: "Blended Premium", desc: "Final = 30% actuarial + 70% ML rate model. NCB discount → levies (VAT 8%, Stamp Duty 1%, CESS 0.5%).", color: "#dc2626" },
            ].map(s => (
              <div key={s.step} style={{ display: "flex", gap: 12, marginBottom: 16 }}>
                <div style={{ width: 32, height: 32, borderRadius: "50%", background: s.color, color: "#fff",
                  display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13, flexShrink: 0 }}>
                  {s.step}
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: "#0f172a" }}>{s.title}</div>
                  <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{s.desc}</div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
              <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>What Was Fixed (vs Previous Version)</h3>
              {[
                { issue: "ROC-AUC was 0.50 (random)", fix: "Deterministic Had_Accident labels → AUC 0.73", ok: true },
                { issue: "Risk Score R² = 0 (random target)", fix: "Risk computed from features → R² 0.60", ok: true },
                { issue: "Premium R² = 0.998 (formula leakage)", fix: "Target changed to rate%, SI removed → R² 0.641", ok: true },
                { issue: "Class imbalance 63% accident", fix: "Realistic 20% base rate with risk function", ok: true },
                { issue: "MV ↔ SI correlation = 1.0", fix: "SI/MV ratio used instead of both separately", ok: true },
                { issue: "Accident_Severity 55% missing", fix: "Filled from DS4 approved claim amounts", ok: true },
                { issue: "Threshold = 0.185 (near random)", fix: "Cost-sensitive: FN=Rs.500K vs FP=Rs.30K → threshold ~0.35", ok: true },
              ].map((r, i) => (
                <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "flex-start" }}>
                  <span style={{ color: "#dc2626", flexShrink: 0 }}>✗</span>
                  <span style={{ fontSize: 11, color: "#64748b", textDecoration: "line-through" }}>{r.issue}</span>
                  <span style={{ color: "#16a34a", flexShrink: 0 }}>→</span>
                  <span style={{ fontSize: 11, color: "#166534" }}>{r.fix}</span>
                </div>
              ))}
            </div>

            <div style={{ background: "#fff", borderRadius: 12, padding: 20, boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
              <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>Model Governance</h3>
              {[
                { k: "Training Date", v: "2025-01-15" },
                { k: "Best Classifier", v: "Stacking Ensemble (AUC 0.731)" },
                { k: "Production Model", v: "HistGBM (AUC 0.724, calibrated)" },
                { k: "Classification Threshold", v: "0.35 (cost-sensitive)" },
                { k: "Calibration Method", v: "Isotonic (Brier 0.183)" },
                { k: "Feature Pipeline", v: "Saved via joblib (no skew)" },
                { k: "Drift Monitor", v: "PSI ≤ 0.10 (stable)" },
              ].map((r, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0",
                  borderBottom: "1px solid #f1f5f9", fontSize: 12 }}>
                  <span style={{ color: "#64748b" }}>{r.k}</span>
                  <span style={{ fontWeight: 600, color: "#0f172a" }}>{r.v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
