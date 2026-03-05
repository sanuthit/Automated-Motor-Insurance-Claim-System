import { useState } from "react";

const SIM_DEFAULT = {
  driver_age: 35, years_exp: 10, engine_cc: 1500,
  vehicle_age: 4, ncb: 20, province: "Western",
};

function calcSimRisk(s) {
  let p = 0.12;
  if (s.driver_age < 22) p += 0.26;
  else if (s.driver_age < 26) p += 0.16;
  else if (s.driver_age > 65) p += 0.14;
  if (s.years_exp < 3) p += 0.18;
  else if (s.years_exp > 15) p -= 0.06;
  if (s.engine_cc > 2500) p += 0.10;
  else if (s.engine_cc > 1800) p += 0.05;
  if (s.vehicle_age > 12) p += 0.12;
  else if (s.vehicle_age > 8) p += 0.06;
  p -= s.ncb * 0.0022;
  if (s.province === "Western") p += 0.08;
  else if (s.province === "Southern") p += 0.04;
  return Math.min(95, Math.max(5, Math.round(p * 100)));
}

export default function RiskSimulator() {
  const [sim, setSim] = useState(SIM_DEFAULT);

  const riskScore = calcSimRisk(sim);
  const riskLevel = riskScore < 25 ? "Low" : riskScore < 50 ? "Moderate" : riskScore < 70 ? "High" : "Very High";
  const riskColor = riskScore < 25 ? "#16a34a" : riskScore < 50 ? "#f59e0b" : riskScore < 70 ? "#ea580c" : "#dc2626";

  const SLIDERS = [
    { key: "driver_age",  label: "Driver Age",         min: 18, max: 80,   unit: "yrs" },
    { key: "years_exp",   label: "Years Experience",   min: 0,  max: 45,   unit: "yrs" },
    { key: "engine_cc",   label: "Engine CC",          min: 800,max: 4500, unit: "cc"  },
    { key: "vehicle_age", label: "Vehicle Age",        min: 0,  max: 25,   unit: "yrs" },
    { key: "ncb",         label: "NCB Discount %",     min: 0,  max: 50,   unit: "%"   },
  ];

  const FACTORS = [
    { label: "Age Factor",        val: sim.driver_age < 25 ? 26 : sim.driver_age < 30 ? 16 : sim.driver_age > 65 ? 14 : 0 },
    { label: "Experience Factor", val: sim.years_exp < 3 ? 18 : sim.years_exp > 15 ? -6 : 0 },
    { label: "Engine CC Factor",  val: sim.engine_cc > 2500 ? 10 : sim.engine_cc > 1800 ? 5 : 0 },
    { label: "Vehicle Age Factor",val: sim.vehicle_age > 12 ? 12 : sim.vehicle_age > 8 ? 6 : 0 },
    { label: "NCB Discount",      val: -Math.round(sim.ncb * 0.22) },
    { label: "Province Loading",  val: sim.province === "Western" ? 8 : sim.province === "Southern" ? 4 : 0 },
  ];

  return (
    <div>
      <h1 className="section-title">⚡ Risk Simulator</h1>
      <p className="section-sub">
        Adjust risk factors in real-time to see how the model score changes — based on the trained ML pipeline weights
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 20 }}>
        {/* Sliders panel */}
        <div className="card">
          <div className="card-header"><span className="card-title">Adjust Risk Factors</span></div>
          {SLIDERS.map(s => (
            <div key={s.key} style={{ marginBottom: 20 }}>
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

          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: "#334155", display: "block", marginBottom: 6 }}>Province</label>
            <select value={sim.province} onChange={e => setSim(p => ({ ...p, province: e.target.value }))}
              style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 13 }}>
              {["Western","Central","Southern","Northern","Eastern","North Western","Uva","Sabaragamuwa","North Central"].map(p => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>

          <button onClick={() => setSim(SIM_DEFAULT)}
            style={{ width: "100%", marginTop: 8, padding: "9px 0", borderRadius: 8, border: "1px solid #e2e8f0",
              background: "#f8fafc", color: "#475569", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
            Reset to Defaults
          </button>
        </div>

        {/* Results panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Gauge */}
          <div className="card" style={{ textAlign: "center" }}>
            <div className="card-header"><span className="card-title">Real-Time Risk Score</span></div>
            <div style={{ padding: "8px 0 16px" }}>
              <svg width={180} height={180} viewBox="0 0 180 180" style={{ display: "block", margin: "0 auto" }}>
                <circle cx={90} cy={90} r={70} fill="none" stroke="#f1f5f9" strokeWidth={16} />
                <circle cx={90} cy={90} r={70} fill="none" stroke={riskColor} strokeWidth={16}
                  strokeDasharray={`${(riskScore / 100) * 440} 440`}
                  strokeLinecap="round" transform="rotate(-90 90 90)"
                  style={{ transition: "stroke-dasharray 0.5s ease" }} />
                <text x={90} y={84} textAnchor="middle" fontSize={36} fontWeight={700} fill={riskColor}>{riskScore}</text>
                <text x={90} y={106} textAnchor="middle" fontSize={13} fill="#64748b">{riskLevel} Risk</text>
              </svg>
              <div style={{ display: "inline-block", marginTop: 12, padding: "6px 20px", borderRadius: 20,
                background: riskColor + "20", color: riskColor, fontWeight: 700, fontSize: 14 }}>
                {riskLevel} Risk Category
              </div>
            </div>
          </div>

          {/* Factor breakdown */}
          <div className="card">
            <div className="card-header"><span className="card-title">Risk Factor Breakdown</span></div>
            {FACTORS.map((f, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <span style={{ fontSize: 12, width: 150, color: "#475569" }}>{f.label}</span>
                <div style={{ flex: 1, height: 8, background: "#f1f5f9", borderRadius: 4 }}>
                  <div style={{ height: 8, borderRadius: 4,
                    width: `${Math.min(100, Math.abs(f.val) * 2.5)}%`,
                    background: f.val < 0 ? "#16a34a" : f.val === 0 ? "#94a3b8" : "#dc2626",
                    transition: "width 0.4s ease" }} />
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, width: 40, textAlign: "right",
                  color: f.val < 0 ? "#16a34a" : f.val === 0 ? "#94a3b8" : "#dc2626" }}>
                  {f.val > 0 ? `+${f.val}` : f.val}
                </span>
              </div>
            ))}
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #f1f5f9",
              display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>Total Risk Score</span>
              <span style={{ fontSize: 18, fontWeight: 700, color: riskColor }}>{riskScore} / 100</span>
            </div>
          </div>

          {/* Interpretation */}
          <div className="card">
            <div className="card-header"><span className="card-title">Interpretation</span></div>
            <div style={{ padding: "4px 0" }}>
              {[
                { range: "0–24",  label: "Low Risk",       bg: "#f0fdf4", color: "#166534", desc: "Experienced driver, clean record, low-risk province" },
                { range: "25–49", label: "Moderate Risk",  bg: "#fffbeb", color: "#92400e", desc: "Some risk factors present but manageable" },
                { range: "50–69", label: "High Risk",      bg: "#fff7ed", color: "#9a3412", desc: "Multiple risk factors — higher loading applied" },
                { range: "70–100",label: "Very High Risk", bg: "#fef2f2", color: "#991b1b", desc: "Significant risk — may require review" },
              ].map((r, i) => (
                <div key={i} style={{ display: "flex", gap: 12, marginBottom: 10, padding: "8px 10px",
                  background: riskScore >= parseInt(r.range) && riskScore <= parseInt(r.range.split("–")[1]) ? r.bg : "transparent",
                  borderRadius: 8, border: riskScore >= parseInt(r.range) && riskScore <= parseInt(r.range.split("–")[1]) ? `1px solid ${r.color}40` : "1px solid transparent" }}>
                  <div style={{ background: r.bg, color: r.color, fontWeight: 700, fontSize: 11,
                    padding: "3px 8px", borderRadius: 6, whiteSpace: "nowrap", border: `1px solid ${r.color}40` }}>
                    {r.range}
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: r.color }}>{r.label}</div>
                    <div style={{ fontSize: 11, color: "#64748b" }}>{r.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
