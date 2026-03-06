import { useState, useEffect } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  LineChart, Line, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis
} from 'recharts'
import { FileText, TrendingUp, Shield, Brain, AlertTriangle, CheckCircle, Award, RefreshCw } from 'lucide-react'
import insuranceAPI from '../services/api'

const PROV_COLORS = ['#0f4c81','#e8a020','#1a7a4a','#c0392b','#6c3483','#0e6655','#d68910','#2980b9','#7f8c8d']
const VEH_COLORS  = { Car:'#0f4c81', SUV:'#e8a020', Van:'#1a7a4a', 'Dual Purpose':'#6c3483' }
const RISK_COLORS = ['#1a7a4a','#e8a020','#c0392b']

const fmt = (n) => `Rs. ${Number(n||0).toLocaleString('en-LK',{maximumFractionDigits:0})}`
const fmtK = (n) => n >= 1000000 ? `Rs.${(n/1000000).toFixed(1)}M` : `Rs.${(n/1000).toFixed(0)}K`

// ── Tooltip customiser ────────────────────────────────────────────────────────
const RiskTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background:'#fff', border:'1px solid #e2e8f0', borderRadius:8,
      padding:'10px 14px', boxShadow:'0 4px 12px rgba(0,0,0,.1)', fontSize:12 }}>
      <div style={{ fontWeight:700, marginBottom:4 }}>{label}</div>
      {payload.map((p,i) => (
        <div key={i} style={{ color:p.color||'#334155' }}>
          {p.name}: <strong>{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</strong>
        </div>
      ))}
    </div>
  )
}

// ── Clickable KPI card ────────────────────────────────────────────────────────
function KpiCard({ label, value, icon: Icon, color, bg, sub, onClick, active }) {
  return (
    <div onClick={onClick} className="kpi-card"
      style={{ cursor: onClick ? 'pointer' : 'default',
        outline: active ? `2px solid ${color}` : 'none',
        transform: active ? 'translateY(-2px)' : 'none',
        transition:'all .2s' }}>
      <div className="kpi-icon" style={{ background: bg }}>
        <Icon size={18} color={color} />
      </div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={{ color }}>{value}</div>
      {sub && <div style={{ fontSize:10, color:'#94a3b8', marginTop:2 }}>{sub}</div>}
    </div>
  )
}

// ── Province risk bar with inline mini-bar ────────────────────────────────────
function ProvTable({ data, highlight, onRowClick }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Province</th><th>Policies</th><th>Avg Risk Score</th><th>Claims</th><th>Risk Level</th>
        </tr>
      </thead>
      <tbody>
        {data.map((p,i) => (
          <tr key={i} onClick={() => onRowClick(p.province)}
            style={{ cursor:'pointer', background: highlight===p.province ? '#eff6ff' : 'transparent',
              transition:'background .15s' }}>
            <td style={{ fontWeight:500 }}>{p.province}</td>
            <td>{(p.policy_count||0).toLocaleString()}</td>
            <td>
              <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                <div style={{ flex:1, background:'#f0f4f8', borderRadius:4, height:8 }}>
                  <div style={{ width:`${Math.min(100,(p.avg_risk/80)*100)}%`, height:'100%', borderRadius:4,
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
  )
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [stats,        setStats]        = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [lastUpdated,  setLastUpdated]  = useState(null)
  const [activeChart,  setActiveChart]  = useState('age')   // age | province | occupation | engine
  const [highlightProv,setHighlightProv]= useState(null)
  const [refreshing,   setRefreshing]   = useState(false)

  const load = async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true)
    try {
      const r = await insuranceAPI.getDashboardStats()
      setStats(r.data)
      setLastUpdated(new Date())
    } catch(e) { console.error(e) }
    finally {
      setLoading(false)
      if (showSpinner) setRefreshing(false)
    }
  }

  useEffect(() => {
    load()
    const iv = setInterval(load, 60000)
    return () => clearInterval(iv)
  }, [])

  if (loading) return <div className="loading-overlay"><div className="spinner"/></div>

  const ageRisk    = stats?.age_risk          || []
  const provRisk   = stats?.province_risk     || []
  const claimTypes = stats?.claim_types       || []
  const vehTypes   = stats?.vehicle_types     || []
  const riskDist   = stats?.risk_distribution || []
  const ncbDist    = stats?.ncb_distribution  || []
  const occRisk    = stats?.occupation_risk   || []
  const ccRisk     = stats?.engine_cc_risk    || []
  const featImp    = stats?.feature_importance|| []

  const genderData = [
    { name:'Male',   value: stats?.gender_male   || 0 },
    { name:'Female', value: stats?.gender_female  || 0 },
  ]

  // Province pie for drill-down
  const provPie = provRisk.map((p,i) => ({ name: p.province, value: p.policy_count, fill: PROV_COLORS[i%PROV_COLORS.length] }))

  const act = stats?.actuarial || {}

  const kpis = [
    { label:'Total Policies',    value:(stats?.total_policies||0).toLocaleString(), icon:FileText,      color:'#0f4c81', bg:'#eff6ff',  sub:'All active records' },
    { label:'Avg Premium',       value:fmtK(stats?.avg_premium||0),                 icon:TrendingUp,    color:'#1a7a4a', bg:'#f0fdf4',  sub:'Per policy/year' },
    { label:'Pure Premium',      value:fmtK(act.pure_premium||0),                   icon:Shield,        color:'#e8a020', bg:'#fffbeb',  sub:`freq×sev = ${(act.frequency||0).toFixed(4)} × Rs.${((act.avg_severity||0)/1000).toFixed(0)}K` },
    { label:'Avg Claim',         value:fmtK(stats?.avg_claim_amount||0),             icon:Shield,        color:'#c0392b', bg:'#fef2f2',  sub:'E[severity | claim]' },
    { label:'Claim Frequency',   value:`${((act.frequency||0)*100).toFixed(1)}%`,    icon:AlertTriangle, color:'#c0392b', bg:'#fef2f2',  sub:'P(claim) from DB' },
    { label:'NCB Eligible',      value:`${(stats?.ncb_rate||0).toFixed(1)}%`,         icon:Award,         color:'#0f4c81', bg:'#eff6ff',  sub:'No-claim bonus holders' },
    { label:'Risk Model AUC',    value:(act.model_auc||0).toFixed(4),                icon:Brain,         color:'#6c3483', bg:'#faf5ff',  sub:`from model_metadata.json v${act.model_version||'?'}` },
    { label:'Rate Model R²',     value:(act.rate_r2||0).toFixed(4),                  icon:Brain,         color:'#0e6655', bg:'#f0fdfa',  sub:`Trained on ${(act.n_training||0).toLocaleString()} policies` },
  ]

  const CHART_TABS = [
    { id:'age',       label:'👤 Age vs Risk' },
    { id:'occupation',label:'💼 Occupation Risk' },
    { id:'engine',    label:'⚙️ Engine CC Risk' },
    { id:'ncb',       label:'🏆 NCB Distribution' },
  ]

  const renderMainChart = () => {
    if (activeChart === 'age') return (
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={ageRisk} margin={{ bottom:20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="age_group" tick={{fontSize:12}}
            label={{value:'Driver Age Group', position:'insideBottom', offset:-8, fontSize:11, fill:'#94a3b8'}} />
          <YAxis domain={[0,100]} tick={{fontSize:11}}
            label={{value:'Avg Risk Score', angle:-90, position:'insideLeft', fontSize:11, fill:'#94a3b8'}} />
          <Tooltip content={<RiskTooltip/>} />
          <Bar dataKey="avg_risk" name="Avg Risk Score" radius={[4,4,0,0]}>
            {ageRisk.map((e,i) => (
              <Cell key={i} fill={e.avg_risk>=70?'#c0392b':e.avg_risk>=50?'#e8a020':'#1a7a4a'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
    if (activeChart === 'occupation') return (
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={occRisk} layout="vertical" margin={{left:10}}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
          <XAxis type="number" domain={[0,80]} tick={{fontSize:11}}
            label={{value:'Avg Risk Score', position:'insideBottom', offset:-4, fontSize:10, fill:'#94a3b8'}} />
          <YAxis dataKey="occupation" type="category" tick={{fontSize:10}} width={145} />
          <Tooltip content={<RiskTooltip/>} />
          <Bar dataKey="avg_risk" name="Avg Risk Score" radius={[0,4,4,0]}>
            {occRisk.map((e,i) => (
              <Cell key={i} fill={e.avg_risk>=60?'#c0392b':e.avg_risk>=45?'#e8a020':'#1a7a4a'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
    if (activeChart === 'engine') return (
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={ccRisk} margin={{bottom:20}}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="bucket" tick={{fontSize:11}}
            label={{value:'Engine Displacement', position:'insideBottom', offset:-8, fontSize:10, fill:'#94a3b8'}} />
          <YAxis yAxisId="left" domain={[0,100]} tick={{fontSize:11}}
            label={{value:'Avg Risk Score', angle:-90, position:'insideLeft', fontSize:10, fill:'#94a3b8'}} />
          <YAxis yAxisId="right" orientation="right" tick={{fontSize:11}}
            label={{value:'Policy Count', angle:90, position:'insideRight', fontSize:10, fill:'#94a3b8'}} />
          <Tooltip content={<RiskTooltip/>} />
          <Bar yAxisId="left"  dataKey="avg_risk" name="Avg Risk Score" fill="#e8a020" radius={[4,4,0,0]} />
          <Bar yAxisId="right" dataKey="count"    name="Policy Count"   fill="#0f4c81" radius={[4,4,0,0]} opacity={0.5} />
          <Legend />
        </BarChart>
      </ResponsiveContainer>
    )
    if (activeChart === 'ncb') return (
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={ncbDist} margin={{bottom:20}}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="ncb" tick={{fontSize:11}}
            label={{value:'NCB Discount (%)', position:'insideBottom', offset:-8, fontSize:11, fill:'#94a3b8'}} />
          <YAxis tick={{fontSize:11}}
            label={{value:'Policy Count', angle:-90, position:'insideLeft', fontSize:11, fill:'#94a3b8'}} />
          <Tooltip content={<RiskTooltip/>} />
          <Bar dataKey="count" name="Policies" radius={[4,4,0,0]}>
            {ncbDist.map((e,i) => (
              <Cell key={i} fill={e.ncb===0?'#c0392b':e.ncb>=30?'#1a7a4a':'#0f4c81'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:4 }}>
        <div>
          <h1 className="section-title">📊 Analytics Dashboard</h1>
          <p className="section-sub" style={{ marginBottom:0 }}>
            Live data from database —{' '}
            {lastUpdated
              ? <span style={{color:'#1a7a4a',fontSize:11}}>✓ Updated: {lastUpdated.toLocaleTimeString()}</span>
              : <span style={{color:'#888',fontSize:11}}>Loading…</span>}
          </p>
        </div>
        <button onClick={() => load(true)} disabled={refreshing}
          style={{ display:'flex', alignItems:'center', gap:6, padding:'8px 16px',
            borderRadius:8, border:'1px solid #e2e8f0', background:'#fff',
            color:'#475569', fontWeight:600, fontSize:13, cursor:'pointer', marginTop:4 }}>
          <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {/* KPI Grid */}
      <div className="kpi-grid" style={{ marginTop:20 }}>
        {kpis.map((k,i) => (
          <KpiCard key={i} {...k} />
        ))}
      </div>

      {/* Row 1: Interactive tabbed chart + Risk distribution + Gender */}
      <div style={{ display:'grid', gridTemplateColumns:'2fr 1fr', gap:20, marginBottom:20, marginTop:20 }}>
        <div className="card">
          {/* Tab bar */}
          <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap' }}>
            {CHART_TABS.map(t => (
              <button key={t.id} onClick={() => setActiveChart(t.id)}
                style={{ padding:'6px 14px', borderRadius:20, border:'none', cursor:'pointer',
                  fontSize:12, fontWeight:600, transition:'all .15s',
                  background: activeChart===t.id ? '#0f4c81' : '#f1f5f9',
                  color: activeChart===t.id ? '#fff' : '#475569' }}>
                {t.label}
              </button>
            ))}
          </div>
          {renderMainChart()}
        </div>

        <div style={{ display:'flex', flexDirection:'column', gap:20 }}>
          {/* Risk distribution donut */}
          <div className="card" style={{ flex:1 }}>
            <div className="card-header"><span className="card-title">🎯 Risk Distribution</span></div>
            <ResponsiveContainer width="100%" height={150}>
              <PieChart>
                <Pie data={riskDist} dataKey="count" nameKey="category"
                  cx="50%" cy="50%" innerRadius={40} outerRadius={65}
                  paddingAngle={3}>
                  {riskDist.map((_,i) => <Cell key={i} fill={RISK_COLORS[i]} />)}
                </Pie>
                <Tooltip formatter={(v) => [v.toLocaleString(),'Policies']} />
                <Legend iconSize={9} wrapperStyle={{fontSize:10}} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Gender */}
          <div className="card" style={{ flex:1 }}>
            <div className="card-header"><span className="card-title">👥 Gender Split</span></div>
            <ResponsiveContainer width="100%" height={150}>
              <PieChart>
                <Pie data={genderData} dataKey="value" nameKey="name"
                  cx="50%" cy="50%" innerRadius={40} outerRadius={65}
                  paddingAngle={3}
                  label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}
                  labelLine={false} fontSize={11}>
                  <Cell fill="#0f4c81" />
                  <Cell fill="#e8a020" />
                </Pie>
                <Tooltip formatter={(v)=>[v.toLocaleString(),'Policies']} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Row 2: Claim types + Vehicle breakdown */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:20 }}>
        <div className="card">
          <div className="card-header"><span className="card-title">🏥 Claims by Type</span></div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={claimTypes.slice(0,8)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
              <XAxis type="number" tick={{fontSize:10}}
                label={{value:'Count', position:'insideBottom', offset:-2, fontSize:10, fill:'#94a3b8'}} />
              <YAxis dataKey="type" type="category" tick={{fontSize:10}} width={140} />
              <Tooltip formatter={(v,n) => n==='count'?[v.toLocaleString(),'Claims']:[fmtK(v),'Avg Amount']} />
              <Bar dataKey="count" fill="#0f4c81" radius={[0,4,4,0]} name="count" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-header"><span className="card-title">🚗 Vehicle Type Distribution</span></div>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={vehTypes} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={90}
                label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}
                labelLine={true} fontSize={11}>
                {vehTypes.map((e,i) => (
                  <Cell key={i} fill={VEH_COLORS[e.name] || PROV_COLORS[i%PROV_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v)=>[v.toLocaleString(),'Policies']} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Row 3: Province Risk — clickable rows + province pie drill-down */}
      <div style={{ display:'grid', gridTemplateColumns:'3fr 2fr', gap:20, marginBottom:20 }}>
        <div className="card">
          <div className="card-header">
            <span className="card-title">🗺️ Province Risk Analysis</span>
            {highlightProv && (
              <button onClick={() => setHighlightProv(null)}
                style={{ fontSize:11, padding:'2px 8px', borderRadius:6, border:'1px solid #e2e8f0',
                  background:'#f1f5f9', cursor:'pointer', color:'#475569', marginLeft:8 }}>
                Clear ✕
              </button>
            )}
          </div>
          <ProvTable data={provRisk} highlight={highlightProv} onRowClick={setHighlightProv} />
        </div>
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              {highlightProv ? `📍 ${highlightProv} Province` : '📍 Policy Distribution by Province'}
            </span>
          </div>
          <ResponsiveContainer width="100%" height={310}>
            <PieChart>
              <Pie
                data={highlightProv
                  ? provRisk.filter(p => p.province === highlightProv).map(p => ([
                      {name:'Policies', value: p.policy_count},
                      {name:'Claims',   value: p.claim_count},
                    ])).flat()
                  : provPie}
                dataKey="value" nameKey={highlightProv ? 'name' : 'name'}
                cx="50%" cy="50%" outerRadius={100}
                label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`}
                labelLine={false} fontSize={10}>
                {(highlightProv
                  ? [{fill:'#0f4c81'},{fill:'#e8a020'}]
                  : provPie.map((_,i) => ({fill:PROV_COLORS[i%PROV_COLORS.length]}))
                ).map((c,i) => <Cell key={i} fill={c.fill} />)}
              </Pie>
              <Tooltip formatter={(v)=>[v.toLocaleString(),'Count']} />
              <Legend wrapperStyle={{fontSize:10}} />
            </PieChart>
          </ResponsiveContainer>
          {highlightProv && (() => {
            const p = provRisk.find(x => x.province === highlightProv)
            if (!p) return null
            return (
              <div style={{ padding:'8px 12px', borderTop:'1px solid #f1f5f9', fontSize:12 }}>
                {[['Policies', p.policy_count?.toLocaleString()],
                  ['Claims',   p.claim_count?.toLocaleString()],
                  ['Avg Risk', Number(p.avg_risk).toFixed(1)],
                ].map(([k,v]) => (
                  <div key={k} style={{ display:'flex', justifyContent:'space-between', padding:'3px 0' }}>
                    <span style={{ color:'#64748b' }}>{k}</span>
                    <span style={{ fontWeight:700 }}>{v}</span>
                  </div>
                ))}
              </div>
            )
          })()}
        </div>
      </div>

      {/* Row 4: ML Feature Importance + Radar comparison */}
      {featImp.length > 0 && (
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:20 }}>
          <div className="card">
            <div className="card-header"><span className="card-title">🔬 ML Feature Importance (Risk Model)</span></div>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={featImp.slice(0,8)} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis type="number" tick={{fontSize:10}} tickFormatter={v=>`${(v*100).toFixed(0)}%`}
                  label={{value:'Importance', position:'insideBottom', offset:-2, fontSize:10, fill:'#94a3b8'}} />
                <YAxis dataKey="feature" type="category" tick={{fontSize:9}} width={160} />
                <Tooltip formatter={(v)=>[`${(v*100).toFixed(2)}%`,'Importance']} />
                <Bar dataKey="importance" fill="#6c3483" radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <div className="card-header"><span className="card-title">📋 Portfolio Summary</span></div>
            <div style={{ padding:'8px 0' }}>
              {[
                ['Total Policies',    (stats?.total_policies||0).toLocaleString(),    '#0f4c81'],
                ['Avg Premium',       fmtK(stats?.avg_premium||0),                    '#1a7a4a'],
                ['Claim Frequency',   `${((act.frequency||0)*100).toFixed(2)}% of policies`, '#e8a020'],
                ['Avg Severity',      fmtK(act.avg_severity||0),                      '#c0392b'],
                ['Pure Premium',      fmtK(act.pure_premium||0),                      '#c0392b'],
                ['NCB Holders',       `${(stats?.ncb_rate||0).toFixed(1)}%`,          '#0f4c81'],
                ['High Risk Rate',    `${(stats?.accident_rate||0).toFixed(1)}%`,     '#c0392b'],
                ['Risk Model AUC',    (act.model_auc||0).toFixed(4),                  '#6c3483'],
                ['Rate Model R²',     (act.rate_r2||0).toFixed(4),                    '#0e6655'],
                ['Renewal Model R²',  (act.renewal_r2||0).toFixed(4),                 '#0e6655'],
                ['Model Version',     act.model_version||'unknown',                    '#475569'],
                ['Blend',             act.blend||'35% Act + 65% ML',                  '#475569'],
              ].map(([k,v,c]) => (
                <div key={k} style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
                  padding:'8px 12px', borderBottom:'1px solid #f8fafc' }}>
                  <span style={{ fontSize:13, color:'#475569' }}>{k}</span>
                  <span style={{ fontSize:13, fontWeight:700, color:c }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
