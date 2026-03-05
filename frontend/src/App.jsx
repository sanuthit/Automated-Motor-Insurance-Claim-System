import React from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, FileText, RefreshCw, Shield,
  Brain, ChevronRight, Activity
} from 'lucide-react'
import Dashboard from './pages/Dashboard'
import NewPolicy from './pages/NewPolicy'
import Renewal from './pages/Renewal'
import Claims from './pages/Claims'
import MLInsights from './pages/MLInsights'

const NAV = [
  { path: '/',          label: 'Dashboard',      icon: LayoutDashboard },
  { path: '/policy',    label: 'New Policy',      icon: FileText },
  { path: '/renewal',   label: 'Policy Renewal',  icon: RefreshCw },
  { path: '/claims',    label: 'Claims',          icon: Shield },
  { path: '/ml',        label: 'ML Insights',     icon: Brain },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:8 }}>
              <div style={{ width:32, height:32, background:'linear-gradient(135deg,#e8a020,#f0b830)', borderRadius:8,
                           display:'flex', alignItems:'center', justifyContent:'center' }}>
                <Activity size={18} color="#fff" />
              </div>
              <div>
                <h1>MotorInsure AI</h1>
                <p>IT22271600</p>
              </div>
            </div>
          </div>
          <nav className="sidebar-nav">
            {NAV.map(({ path, label, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                end={path === '/'}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <Icon size={18} className="nav-icon" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div style={{ padding:'16px 20px', borderTop:'1px solid rgba(255,255,255,0.08)' }}>
            <p style={{ color:'rgba(255,255,255,0.4)', fontSize:11 }}>Motor Insurance</p>
            <p style={{ color:'rgba(255,255,255,0.4)', fontSize:11 }}>Risk-Based Premium System</p>
          </div>
        </aside>
        <main className="main-content">
          <Routes>
            <Route path="/"        element={<Dashboard />} />
            <Route path="/policy"  element={<NewPolicy />} />
            <Route path="/renewal" element={<Renewal />} />
            <Route path="/claims"  element={<Claims />} />
            <Route path="/ml"      element={<MLInsights />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
