import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line
} from "recharts";

const SHAP_FEATURES = [
  { feature: "Driver Age",        importance: 0.187, direction: "both", note: "Young (<25) & senior (>65) = higher risk" },
  { feature: "Years Experience",  importance: 0.162, direction: "neg",  note: "More experience = lower risk" },
  { feature: "Province",          importance: 0.141, direction: "both", note: "Western / Southern = higher claim frequency" },
  { feature: "Engine CC",         importance: 0.118, direction: "pos",  note: "Higher CC = higher risk & repair cost" },
  { feature: "Vehicle Age",       importance: 0.109, direction: "pos",  note: "Older vehicle = higher mechanical risk" },
  { feature: "NCB %",             importance: 0.098, direction: "neg",  note: "Higher NCB = historically safe driver" },
  { feature: "Vehicle Type",      importance: 0.087, direction: "both", note: "SUV/DP costlier to repair" },
  { feature: "Vehicle Condition", importance: 0.071, direction: "pos",  note: "Poor condition = higher claim probability" },
  { feature: "SI / Market Value", importance: 0.063, direction: "pos",  note: "Over-insurance flag" },
  { feature: "Occupation",        importance: 0.044, direction: "both", note: "Delivery / transport = higher risk" },
];

const AGE_RISK_DATA = Array.from({ length: 14 }, (_, i) => {
  const age = 18 + i * 4;
  let risk = 0.12;
  if (age < 22) risk = 0.38;
  else if (age < 26) risk = 0.28;
  else if (age < 35) risk = 0.15;
  else if (age < 50) risk = 0.10;
  else if (age < 60) risk = 0.12;
  else if (age < 70) risk = 0.18;
  else risk = 0.26;
  return { age: `${age}`, risk: parseFloat((risk * 100).toFixed(1)) };
});

export default function ShapInsights() {
  return (
    <div>
      <h1 className="section-title">🧠 SHAP Feature Importance</h1>
      <p className="section-sub">
        Global explainability — how each feature contributes to risk prediction across all policies
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <div className="card">
          <div className="card-header">
            <span className="card-title">Global SHAP Feature Importance</span>
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={[...SHAP_FEATURES].reverse()} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" domain={[0, 0.25]} tickFormatter={v => v.toFixed(2)} tick={{ fontSize: 10 }}
                label={{ value: "Mean |SHAP value|", position: "insideBottom", offset: -2, fontSize: 11, fill: "#94a3b8" }} />
              <YAxis type="category" dataKey="feature" tick={{ fontSize: 11 }} width={140} />
              <Tooltip formatter={v => [v.toFixed(4), "SHAP Importance"]} />
              <Bar dataKey="importance" fill="#2563eb" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Feature Effect Direction</span>
          </div>
          {SHAP_FEATURES.map((f, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{f.feature}</span>
                <span style={{
                  fontSize: 11, fontWeight: 600,
                  color: f.direction === "neg" ? "#16a34a" : f.direction === "pos" ? "#dc2626" : "#f59e0b"
                }}>
                  {f.direction === "neg" ? "↓ Risk Reducer" : f.direction === "pos" ? "↑ Risk Increaser" : "↕ Bidirectional"}
                </span>
              </div>
              <div style={{ height: 6, background: "#e2e8f0", borderRadius: 3, marginBottom: 3 }}>
                <div style={{
                  height: 6, borderRadius: 3, width: `${f.importance * 500}%`,
                  background: f.direction === "neg" ? "#16a34a" : f.direction === "pos" ? "#dc2626" : "#f59e0b"
                }} />
              </div>
              <div style={{ fontSize: 11, color: "#64748b" }}>{f.note}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Accident Risk by Driver Age</span>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={AGE_RISK_DATA}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="age" tick={{ fontSize: 11 }}
              label={{ value: "Driver Age (years)", position: "insideBottom", offset: -3, fontSize: 11, fill: "#94a3b8" }} />
            <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }}
              label={{ value: "Accident Risk %", angle: -90, position: "insideLeft", fontSize: 11, fill: "#94a3b8" }} />
            <Tooltip formatter={v => [`${v}%`, "Accident Risk"]} />
            <Line type="monotone" dataKey="risk" stroke="#dc2626" strokeWidth={2} dot={{ r: 3 }} name="Accident Risk %" />
          </LineChart>
        </ResponsiveContainer>
        <p style={{ fontSize: 11, color: "#94a3b8", marginTop: 8, padding: "0 4px" }}>
          Young drivers (&lt;25) and senior drivers (&gt;65) show significantly elevated risk — consistent with Sri Lanka traffic statistics.
        </p>
      </div>
    </div>
  );
}
