import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'

import MapPage        from './pages/MapPage'
import ResultsPage    from './pages/ResultsPage'
import TelemetryPage  from './pages/TelemetryPage'
import ComparisonPage from './pages/ComparisonPage'
import PredictPage    from './pages/PredictPage'

const LINKS = [
  { to: '/',           label: '🌍 Carte & Dates' },
  { to: '/results',    label: '🏆 Résultats' },
  { to: '/telemetry',  label: '📈 Télémétrie' },
  { to: '/comparison', label: '🗺️ Comparaison' },
  { to: '/predict',    label: '🔮 Prédictions' },
]

export default function App() {
  return (
    <div className="app-layout">
      <nav className="navbar">
        <NavLink to="/" className="navbar-brand" style={{ lineHeight:1.1 }}>
          <span style={{ display:'block', fontSize:'1.5rem' }}>F1</span>
          <span style={{ display:'block', fontSize:'0.9rem', letterSpacing:'0.15em' }}>BIG SEB</span>
        </NavLink>
        <ul className="navbar-links">
          {LINKS.map(({ to, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                className={({ isActive }) => isActive ? 'active' : ''}
              >
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="main-content">
        <Routes>
          <Route path="/"           element={<MapPage />} />
          <Route path="/results"    element={<ResultsPage />} />
          <Route path="/telemetry"  element={<TelemetryPage />} />
          <Route path="/comparison" element={<ComparisonPage />} />
          <Route path="/predict"    element={<PredictPage />} />
        </Routes>
      </main>
    </div>
  )
}
