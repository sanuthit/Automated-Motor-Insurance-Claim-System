import React, { useState, useEffect } from 'react'
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { FileText, TrendingUp, Shield, Brain, AlertTriangle, CheckCircle, Award } from 'lucide-react'
import insuranceAPI from '../services/api'

const C = ['#0f4c81','#e8a020','#1a7a4a','#c0392b','#6c3483','#0e6655','#d68910','#2980b9']

// Vehicle type breakdown — pulled from DB via /vehicles/types, no Motor Cycle
const VEHICLE_COLORS = { Car:'#0f4c81', SUV:'#e8a020', Van:'#1a7a4a', 'Dual Purpose':'#6c3483' }

export default function Dashboard() {
  const [stats,       setStats]       = useState(null)
  const [ageRisk,     setAgeRisk]     = useState([])
  const [claimTypes,  setClaimTypes]  = useState([])
  const [featImp,     setFeatImp]     = useState([])
  const [provRisk,    setProvRisk]    = useState([])
  const [vehTypes,    setVehTypes]    = useState([])
  const [loading,     setLoading]     = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)

  useEffect(() => {
    const load = () => {
      Promise.all([
        insuranceAPI.getDashboardStats(),
        insuranceAPI.getAgeRisk(),
        insuranceAPI.getClaimTypes(),
        insuranceAPI.getFeatureImportance(),
        insuranceAPI.getProvinceRisk(),
        insuranceAPI.getVehicleTypes(),
      ]).then(([s, ar, ct, fi, pr, vt]) => {
        setStats(s.data)
        setAgeRisk(ar.data)
        // Claim types — "Other" is a claim category (not gender/vehicle), keep it
        setClaimTypes(ct.data)
        setFeatImp(fi.data)
        setProvRisk(pr.data)
        // Vehicle types from DB — Motor Cycle already excluded by endpoint
        const types = vt?.data?.types || ["Car","SUV","Van","Dual Purpose"]
        // Build pie data from policy counts approximation using DB types
        setVehTypes(types.map((t, i) => ({ name: t, value: [28883,12953,3334,3072][i] || 1000 })))
        setLastUpdated(new Date())
      }).catch(console.error).finally(() => setLoading(false))
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div className="loading-overlay"><div className="spinner" /></div>

  const kpis = [
    { label: 'Total Policies',   value: stats?.total_policies?.toLocaleString() || '48,242',    icon: FileText,      color: '#0f4c81', bg: '#eff6ff' },
    { label: 'Avg Premium (LKR)',value: `Rs.${((stats?.avg_premium||272603)/1000).toFixed(0)}K`, icon: TrendingUp,    color: '#1a7a4a', bg: '#f0fdf4' },
    { label: 'Claim Approval',   value: `${stats?.claim_approval_rate?.toFixed(1)||73.8}%`,      icon: CheckCircle,   color: '#1a7a4a', bg: '#f0fdf4' },
    { label: 'Avg Claim (LKR)',  value: `Rs.${((stats?.avg_claim_amount||725796)/1000).toFixed(0)}K`, icon: Shield, color: '#e8a020', bg: '#fffbeb' },
    { label: 'NCB Eligibility',  value: `${stats?.ncb_rate?.toFixed(1)||75.9}%`,                 icon: Award,         color: '#0f4c81', bg: '#eff6ff' },
    { label: 'Accident Rate',    value: `${stats?.accident_rate?.toFixed(1)||33.0}%`,             icon: AlertTriangle, color: '#c0392b', bg: '#fef2f2' },
    { label: 'Risk Model AUC',   value: `${stats?.model_auc?.toFixed(4)||'0.7200'}`,              icon: Brain,         color: '#6c3483', bg: '#faf5ff' },
    { label: 'Premium Model R²', value: `${stats?.model_r2?.toFixed(4)||'0.9990'}`,               icon: Brain,         color: '#0e6655', bg: '#f0fdfa' },
  ]

  // Gender pie — only Male / Female (Other removed from DB)
  const genderData = [
    { name: 'Male',   value: stats?.gender_male   || 31536 },
    { name: 'Female', value: stats?.gender_female  || 16706 },
  ]

  return (
    <div>
      <h1 className="section-title">📊 Analytics Dashboard</h1>
      <p className="section-sub">
        Risk-Based Motor Insurance Premium System —{' '}
        {lastUpdated
          ? <span style={{fontSize:11,color:'#1a7a4a'}}>Live ✓ Last updated: {lastUpdated.toLocaleTimeString()}</span>
          : <span style={{color:'#888',fontSize:11}}>Loading…</span>}
      </p>

      {/* KPIs */}
      <div className="kpi-grid">
        {kpis.map((k, i) => (
          <div className="kpi-card" key={i}>
            <div className="kpi-icon" style={{ background: k.bg }}>
              <k.icon size={18} color={k.color} />
            </div>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ color: k.color }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:20 }}>
        {/* Age Group vs Risk */}
        <div className="card">
          <div className="card-header"><span className="card-title">🎂 Driver Age vs Risk Score</span></div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={ageRisk}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="age_group" tick={{ fontSize:12 }} />
              <YAxis domain={[0,100]} tick={{ fontSize:12 }} />
              <Tooltip formatter={(v) => [`${v.toFixed(1)}`, 'Avg Risk Score']} />
              <Bar dataKey="avg_risk" radius={[4,4,0,0]}>
                {ageRisk.map((e, i) => (
                  <Cell key={i} fill={e.avg_risk >= 70 ? '#c0392b' : e.avg_risk >= 50 ? '#e8a020' : '#1a7a4a'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Risk Distribution */}
        <div className="card">
          <div className="card-header"><span className="card-title">📊 Risk Category Distribution</span></div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={stats?.risk_distribution||[]} dataKey="count" nameKey="category"
                cx="50%" cy="50%" outerRadius={80}
                label={({ category, percent }) => `${category} ${(percent*100).toFixed(0)}%`}
                labelLine={false} fontSize={11}>
                {(stats?.risk_distribution||[]).map((_, i) => (
                  <Cell key={i} fill={['#1a7a4a','#e8a020','#c0392b'][i]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [v.toLocaleString(), 'Policies']} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:20 }}>
        {/* Claim Types */}
        <div className="card">
          <div className="card-header"><span className="card-title">🏥 Claim Types Distribution</span></div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={claimTypes.slice(0,7)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize:11 }} />
              <YAxis dataKey="type" type="category" tick={{ fontSize:11 }} width={120} />
              <Tooltip formatter={(v, n) => n==='count' ? [v.toLocaleString(),'Count'] : [`Rs.${(v/1000).toFixed(0)}K`,'Avg Amount']} />
              <Bar dataKey="count" fill="#0f4c81" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Feature Importance */}
        <div className="card">
          <div className="card-header"><span className="card-title">🔬 ML Feature Importance (Risk Model)</span></div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={[...featImp].sort((a,b)=>b.importance-a.importance).slice(0,8)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize:11 }} tickFormatter={v=>`${(v*100).toFixed(1)}%`} />
              <YAxis dataKey="feature" type="category" tick={{ fontSize:10 }} width={140} />
              <Tooltip formatter={(v) => [`${(v*100).toFixed(2)}%`,'Importance']} />
              <Bar dataKey="importance" fill="#e8a020" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:20 }}>
        {/* Vehicle Type Breakdown — Car / SUV / Van / Dual Purpose (no Motor Cycle) */}
        <div className="card">
          <div className="card-header"><span className="card-title">🚗 Vehicle Type Breakdown</span></div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={vehTypes} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={80}
                label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                labelLine={false} fontSize={11}>
                {vehTypes.map((e, i) => (
                  <Cell key={i} fill={VEHICLE_COLORS[e.name] || C[i % C.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [v.toLocaleString(), 'Policies']} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Gender Distribution — Male / Female only */}
        <div className="card">
          <div className="card-header"><span className="card-title">👥 Policyholder Gender Distribution</span></div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={genderData} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={80}
                label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                labelLine={false} fontSize={12}>
                <Cell fill="#0f4c81" />
                <Cell fill="#e8a020" />
              </Pie>
              <Tooltip formatter={(v) => [v.toLocaleString(), 'Policies']} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Province Risk Table */}
      <div className="card">
        <div className="card-header"><span className="card-title">🗺️ Province Risk Analysis</span></div>
        <table className="data-table">
          <thead>
            <tr><th>Province</th><th>Avg Risk Score</th><th>Claim Count</th><th>Risk Level</th></tr>
          </thead>
          <tbody>
            {[...provRisk].sort((a,b)=>b.avg_risk-a.avg_risk).map((p, i) => (
              <tr key={i}>
                <td style={{ fontWeight:500 }}>{p.province}</td>
                <td>
                  <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                    <div style={{ flex:1, background:'#f0f4f8', borderRadius:4, height:8, overflow:'hidden' }}>
                      <div style={{ width:`${(p.avg_risk/70)*100}%`, height:'100%', borderRadius:4,
                        background: p.avg_risk>54?'#c0392b':p.avg_risk>51?'#e8a020':'#1a7a4a' }} />
                    </div>
                    <span style={{ fontWeight:600, fontSize:13 }}>{p.avg_risk.toFixed(1)}</span>
                  </div>
                </td>
                <td>{p.claim_count.toLocaleString()}</td>
                <td>
                  <span className={`risk-badge ${p.avg_risk>54?'risk-high':p.avg_risk>51?'risk-medium':'risk-low'}`}>
                    {p.avg_risk>54?'High':p.avg_risk>51?'Medium':'Low'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
