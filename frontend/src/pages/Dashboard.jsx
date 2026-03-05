import React, { useState, useEffect, useMemo } from 'react'
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { FileText, TrendingUp, Shield, Brain, AlertTriangle, CheckCircle, Award, Filter } from 'lucide-react'
import insuranceAPI from '../services/api'

const C = ['#0f4c81','#e8a020','#1a7a4a','#c0392b','#6c3483','#0e6655','#d68910','#2980b9']
const VEHICLE_COLORS = { Car:'#0f4c81', SUV:'#e8a020', Van:'#1a7a4a', 'Dual Purpose':'#6c3483' }

export default function Dashboard() {
  const [stats,       setStats]       = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)
  // Filters
  const [filterProvince, setFilterProvince] = useState('All')
  const [filterVehicle,  setFilterVehicle]  = useState('All')
  const [filterRisk,     setFilterRisk]     = useState('All')

  useEffect(() => {
    const load = () => {
      insuranceAPI.getDashboardStats()
        .then(r => {
          setStats(r.data)
          setLastUpdated(new Date())
        })
        .catch(console.error)
        .finally(() => setLoading(false))
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  // All data comes from single /dashboard/stats endpoint
  const ageRisk    = stats?.age_risk     || []
  const provRisk   = stats?.province_risk || []
  const claimTypes = stats?.claim_types  || []
  const featImp    = stats?.feature_importance || []
  const vehTypes   = stats?.vehicle_types || []

  // Province filter applied to province table
  const filteredProv = useMemo(() => {
    let data = [...provRisk]
    if (filterProvince !== 'All') data = data.filter(p => p.province === filterProvince)
    if (filterRisk === 'High')   data = data.filter(p => p.avg_risk >= 70)
    if (filterRisk === 'Medium') data = data.filter(p => p.avg_risk >= 40 && p.avg_risk < 70)
    if (filterRisk === 'Low')    data = data.filter(p => p.avg_risk < 40)
    return data.sort((a,b) => b.avg_risk - a.avg_risk)
  }, [provRisk, filterProvince, filterRisk])

  // Vehicle filter applied to vehicle pie
  const filteredVeh = useMemo(() => {
    if (filterVehicle === 'All') return vehTypes
    return vehTypes.filter(v => v.name === filterVehicle)
  }, [vehTypes, filterVehicle])

  const provinces  = ['All', ...provRisk.map(p => p.province)]
  const vehicleOpts = ['All', ...vehTypes.map(v => v.name)]

  if (loading) return <div className="loading-overlay"><div className="spinner" /></div>

  const kpis = [
    { label: 'Total Policies',   value: stats?.total_policies?.toLocaleString() || '—',        icon: FileText,      color: '#0f4c81', bg: '#eff6ff' },
    { label: 'Avg Premium (LKR)',value: stats?.avg_premium ? `Rs.${(stats.avg_premium/1000).toFixed(0)}K` : '—', icon: TrendingUp, color: '#1a7a4a', bg: '#f0fdf4' },
    { label: 'Claim Approval',   value: stats?.claim_approval_rate != null ? `${stats.claim_approval_rate.toFixed(1)}%` : '—', icon: CheckCircle, color: '#1a7a4a', bg: '#f0fdf4' },
    { label: 'Avg Claim (LKR)',  value: stats?.avg_claim_amount ? `Rs.${(stats.avg_claim_amount/1000).toFixed(0)}K` : '—', icon: Shield, color: '#e8a020', bg: '#fffbeb' },
    { label: 'NCB Eligibility',  value: stats?.ncb_rate != null ? `${stats.ncb_rate.toFixed(1)}%` : '—', icon: Award, color: '#0f4c81', bg: '#eff6ff' },
    { label: 'High Risk Rate',   value: stats?.accident_rate != null ? `${stats.accident_rate.toFixed(1)}%` : '—', icon: AlertTriangle, color: '#c0392b', bg: '#fef2f2' },
    { label: 'Risk Model AUC',   value: stats?.model_auc != null ? `${Number(stats.model_auc).toFixed(4)}` : '—', icon: Brain, color: '#6c3483', bg: '#faf5ff' },
    { label: 'Premium Model R²', value: stats?.model_r2 != null  ? `${Number(stats.model_r2).toFixed(4)}`  : '—', icon: Brain, color: '#0e6655', bg: '#f0fdfa' },
  ]

  const genderData = [
    { name: 'Male',   value: stats?.gender_male   || 0 },
    { name: 'Female', value: stats?.gender_female  || 0 },
  ]

  const selStyle = {
    padding: '6px 10px', borderRadius: 6, border: '1px solid #e2e8f0',
    fontSize: 12, background: '#fff', cursor: 'pointer'
  }

  return (
    <div>
      <h1 className="section-title">📊 Analytics Dashboard</h1>
      <p className="section-sub">
        Live data from database —{' '}
        {lastUpdated
          ? <span style={{fontSize:11,color:'#1a7a4a'}}>✓ Updated: {lastUpdated.toLocaleTimeString()}</span>
          : <span style={{color:'#888',fontSize:11}}>Loading…</span>}
      </p>

      {/* Filters */}
      <div style={{ display:'flex', gap:12, alignItems:'center', marginBottom:20,
        background:'#fff', padding:'12px 16px', borderRadius:10, boxShadow:'0 1px 4px rgba(0,0,0,.06)' }}>
        <Filter size={16} color="#64748b" />
        <span style={{fontSize:13,fontWeight:600,color:'#475569'}}>Filters:</span>
        <select value={filterProvince} onChange={e=>setFilterProvince(e.target.value)} style={selStyle}>
          {provinces.map(p=><option key={p}>{p}</option>)}
        </select>
        <select value={filterVehicle} onChange={e=>setFilterVehicle(e.target.value)} style={selStyle}>
          {vehicleOpts.map(v=><option key={v}>{v}</option>)}
        </select>
        <select value={filterRisk} onChange={e=>setFilterRisk(e.target.value)} style={selStyle}>
          {['All','High','Medium','Low'].map(r=><option key={r}>{r} Risk</option>)}
        </select>
        {(filterProvince!=='All'||filterVehicle!=='All'||filterRisk!=='All') && (
          <button onClick={()=>{setFilterProvince('All');setFilterVehicle('All');setFilterRisk('All')}}
            style={{...selStyle, background:'#f1f5f9', color:'#64748b'}}>
            Clear
          </button>
        )}
      </div>

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
              <XAxis dataKey="age_group" tick={{ fontSize:12 }} label={{ value:'Age Group (years)', position:'insideBottom', offset:-2, fontSize:11, fill:'#94a3b8' }} />
              <YAxis domain={[0,100]} tick={{ fontSize:12 }} label={{ value:'Avg Risk Score', angle:-90, position:'insideLeft', fontSize:11, fill:'#94a3b8' }} />
              <Tooltip formatter={(v) => [`${Number(v).toFixed(1)}`, 'Avg Risk Score']} />
              <Bar dataKey="avg_risk" radius={[4,4,0,0]} name="Avg Risk Score">
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
                label={({ category, percent }) => `${category?.split(' ')[0]} ${(percent*100).toFixed(0)}%`}
                labelLine={false} fontSize={11}>
                {(stats?.risk_distribution||[]).map((_, i) => (
                  <Cell key={i} fill={['#1a7a4a','#e8a020','#c0392b'][i]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [v.toLocaleString(), 'Policies']} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:20 }}>
        {/* Claim Types */}
        <div className="card">
          <div className="card-header"><span className="card-title">🏥 Claim Types Distribution</span></div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={claimTypes.slice(0,8)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize:11 }} label={{ value:'Number of Claims', position:'insideBottom', offset:-2, fontSize:10, fill:'#94a3b8' }} />
              <YAxis dataKey="type" type="category" tick={{ fontSize:10 }} width={130} />
              <Tooltip formatter={(v, n) => n==='count' ? [v.toLocaleString(),'Claims'] : [`Rs.${(v/1000).toFixed(0)}K`,'Avg Amount']} />
              <Bar dataKey="count" fill="#0f4c81" radius={[0,4,4,0]} name="count" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Feature Importance */}
        <div className="card">
          <div className="card-header"><span className="card-title">🔬 ML Feature Importance (Risk Model)</span></div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={[...featImp].sort((a,b)=>b.importance-a.importance).slice(0,8)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize:11 }} tickFormatter={v=>`${(v*100).toFixed(0)}%`}
                label={{ value:'Importance (%)', position:'insideBottom', offset:-2, fontSize:10, fill:'#94a3b8' }} />
              <YAxis dataKey="feature" type="category" tick={{ fontSize:10 }} width={160} />
              <Tooltip formatter={(v) => [`${(v*100).toFixed(2)}%`,'Importance']} />
              <Bar dataKey="importance" fill="#e8a020" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:20 }}>
        {/* Vehicle Type Breakdown — from DB */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">🚗 Vehicle Type Breakdown</span>
            {filterVehicle !== 'All' && <span style={{fontSize:11,color:'#2563eb',marginLeft:8}}>Filtered: {filterVehicle}</span>}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={filteredVeh} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={80}
                label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                labelLine={false} fontSize={11}>
                {filteredVeh.map((e, i) => (
                  <Cell key={i} fill={VEHICLE_COLORS[e.name] || C[i % C.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [v.toLocaleString(), 'Policies']} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Gender Distribution */}
        <div className="card">
          <div className="card-header"><span className="card-title">👥 Policyholder Gender Distribution</span></div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={genderData} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={80}
                label={({ name, value, percent }) => `${name}: ${value.toLocaleString()} (${(percent*100).toFixed(0)}%)`}
                labelLine={true} fontSize={12}>
                <Cell fill="#0f4c81" />
                <Cell fill="#e8a020" />
              </Pie>
              <Tooltip formatter={(v) => [v.toLocaleString(), 'Policies']} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Province Risk Table — filterable */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">🗺️ Province Risk Analysis</span>
          {filterProvince !== 'All' && <span style={{fontSize:11,color:'#2563eb',marginLeft:8}}>Filtered: {filterProvince}</span>}
          {filterRisk !== 'All' && <span style={{fontSize:11,color:'#2563eb',marginLeft:8}}>| Risk: {filterRisk}</span>}
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Province</th>
              <th>Policy Count</th>
              <th>Avg Risk Score</th>
              <th>Claim Count</th>
              <th>Risk Level</th>
            </tr>
          </thead>
          <tbody>
            {filteredProv.length === 0 ? (
              <tr><td colSpan={5} style={{textAlign:'center',color:'#94a3b8',padding:20}}>No data for selected filters</td></tr>
            ) : filteredProv.map((p, i) => (
              <tr key={i}>
                <td style={{ fontWeight:500 }}>{p.province}</td>
                <td>{(p.policy_count||0).toLocaleString()}</td>
                <td>
                  <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                    <div style={{ flex:1, background:'#f0f4f8', borderRadius:4, height:8, overflow:'hidden' }}>
                      <div style={{ width:`${(p.avg_risk/80)*100}%`, height:'100%', borderRadius:4,
                        background: p.avg_risk>=70?'#c0392b':p.avg_risk>=40?'#e8a020':'#1a7a4a' }} />
                    </div>
                    <span style={{ fontWeight:600, fontSize:13 }}>{Number(p.avg_risk).toFixed(1)}</span>
                  </div>
                </td>
                <td>{(p.claim_count||0).toLocaleString()}</td>
                <td>
                  <span className={`risk-badge ${p.avg_risk>=70?'risk-high':p.avg_risk>=40?'risk-medium':'risk-low'}`}>
                    {p.avg_risk>=70?'High':p.avg_risk>=40?'Medium':'Low'}
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
