import React, { useState, useEffect } from 'react'
import Plot from 'react-plotly.js'
import { YEARS, PLOTLY_LAYOUT, PLOTLY_CONFIG } from '../constants'
import { apiFetch } from '../hooks/useApi'

const ALL_YEARS = Array.from(
  { length: new Date().getFullYear() - 2017 },
  (_, i) => new Date().getFullYear() - i
)

export default function TelemetryPage() {
  const [year,         setYear]         = useState(ALL_YEARS[0])
  const [circuit,      setCircuit]      = useState('')
  const [races,        setRaces]        = useState([])
  const [loadingRaces, setLoadingRaces] = useState(false)
  const [isSprint,     setIsSprint]     = useState(false)
  const [hasSprint,    setHasSprint]    = useState(false)
  const [drivers,      setDrivers]      = useState([])
  const [selected,     setSelected]     = useState([])
  const [telData,      setTelData]      = useState({})
  const [posData,      setPosData]      = useState(null)
  const [loading,      setLoading]      = useState(false)
  const [loadingDrv,   setLoadingDrv]   = useState(null)
  const [error,        setError]        = useState(null)

  useEffect(() => {
    setLoadingRaces(true)
    setCircuit('')
    setIsSprint(false)
    setHasSprint(false)
    fetch('/api/gp-history')
      .then(r => r.json())
      .then(d => {
        const yr = (d.races || []).filter(r => r.year === year).sort((a, b) => a.round - b.round)
        setRaces(yr)
        if (yr.length > 0) setCircuit(yr[yr.length - 1].raceName)
        setLoadingRaces(false)
      })
      .catch(() => setLoadingRaces(false))
  }, [year])

  const loadSession = async () => {
    setLoading(true); setError(null)
    setTelData({}); setDrivers([]); setSelected([]); setPosData(null)
    try {
      const d = await apiFetch(`/api/sessions/${year}/${encodeURIComponent(circuit)}?sprint=${isSprint}`)
      setDrivers(d.drivers || [])
      setSelected(d.drivers || [])

      // Check sprint availability
      fetch(`/api/sprint/${year}/${encodeURIComponent(circuit)}`)
        .then(r => r.json()).then(s => setHasSprint(s.available || false))
        .catch(() => setHasSprint(false))

      // Load positions
      fetch(`/api/positions/${year}/${encodeURIComponent(circuit)}?sprint=${isSprint}`)
        .then(r => r.json()).then(p => setPosData(p))
        .catch(() => setPosData(null))

      // Load telemetry for all drivers
      const tel = {}
      for (const drv of (d.drivers || [])) {
        setLoadingDrv(drv)
        try {
          tel[drv] = await apiFetch(`/api/telemetry/${year}/${encodeURIComponent(circuit)}/${drv}?sprint=${isSprint}`)
        } catch {}
      }
      setTelData(tel)
      setLoadingDrv(null)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const toggleDriver = (drv) =>
    setSelected(s => s.includes(drv) ? s.filter(d => d !== drv) : [...s, drv])

  const activeTel = selected.filter(d => telData[d])

  // ── Positions chart ───────────────────────────────────────────────────────
  const posChart = posData ? (() => {
    const { sc_laps = [], vsc_laps = [] } = posData
    const shapes = [
      ...sc_laps.map(lap => ({
        type:'line', x0:lap, x1:lap, y0:0, y1:1, yref:'paper',
        line:{ color:'rgba(255,210,0,0.3)', width:16 }
      })),
      ...vsc_laps.map(lap => ({
        type:'line', x0:lap, x1:lap, y0:0, y1:1, yref:'paper',
        line:{ color:'rgba(255,150,0,0.2)', width:16 }
      })),
    ]
    return {
      data: [
        ...(sc_laps.length ? [{
          x:[null], y:[null], name:'🟡 Safety Car', type:'scatter', mode:'lines',
          line:{ color:'rgba(255,210,0,0.7)', width:8 }, showlegend:true,
        }] : []),
        ...(vsc_laps.length ? [{
          x:[null], y:[null], name:'🟠 VSC', type:'scatter', mode:'lines',
          line:{ color:'rgba(255,150,0,0.6)', width:8 }, showlegend:true,
        }] : []),
        ...posData.drivers.map(d => ({
          x: d.laps, y: d.positions,
          name: d.driver, type:'scatter', mode:'lines',
          line:{ color: d.color, width:2, dash: d.dash || 'solid' },
          hovertemplate:`<b>${d.driver}</b> T%{x} — P%{y}<extra></extra>`,
        })),
      ],
      layout: {
        ...PLOTLY_LAYOUT,
        height: 420,
        shapes,
        title:{ text:'POSITIONS EN COURSE', font:{family:'Barlow Condensed',size:12,color:'#e8002d'} },
        xaxis:{ ...PLOTLY_LAYOUT.xaxis, title:{text:'Tour',font:{color:'#888',size:10}} },
        yaxis:{ ...PLOTLY_LAYOUT.yaxis, autorange:'reversed',
          title:{text:'Position',font:{color:'#888',size:10}},
          tickvals:[1,3,5,10,15,20], dtick:1 },
        legend:{ orientation:'v', x:1.02, y:1, font:{size:10,color:'#ccc'},
                 bgcolor:'rgba(0,0,0,0)' },
        margin:{ l:55, r:120, t:40, b:40 },
      }
    }
  })() : null

  // ── Telemetry charts ──────────────────────────────────────────────────────
  const makeChart = (channel, title, yTitle) => ({
    data: activeTel.map(drv => {
      const t = telData[drv]
      return {
        x: t.distance, y: t[channel],
        name: drv, type:'scatter', mode:'lines',
        line:{ color:t.color, width:1.8, dash: t.dash || 'solid' },
        hovertemplate:`<b>${drv}</b> — %{y:.1f}<extra></extra>`,
      }
    }),
    layout: {
      ...PLOTLY_LAYOUT,
      height: channel === 'speed' ? 280 : 160,
      title:{ text:title, font:{family:'Barlow Condensed',size:12,color:'#e8002d'} },
      xaxis:{ ...PLOTLY_LAYOUT.xaxis,
        title: channel === 'gear' ? {text:'Distance (m)',font:{color:'#888',size:10}} : undefined },
      yaxis:{ ...PLOTLY_LAYOUT.yaxis,
        title:{text:yTitle,font:{color:'#888',size:10}} },
    }
  })

  const charts = [
    makeChart('speed', 'VITESSE (km/h)', 'km/h'),
    makeChart('brake', 'FREIN (%)',      '%'),
    makeChart('gear',  'RAPPORT',        'Rapport'),
  ]

  return (
    <div>
      <h1 className="condensed" style={{ fontSize:'2rem', fontWeight:900,
        textTransform:'uppercase', marginBottom:'0.4rem',
        background:'linear-gradient(90deg,#e8002d,#ff6b6b,#fff)',
        WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>
        Télémétrie
      </h1>
      <p style={{ color:'var(--muted)', fontSize:'0.85rem', marginBottom:'1.5rem' }}>
        Positions en course tour par tour + données télémétriques sur le{' '}
        <strong style={{color:'var(--text)'}}>meilleur tour en course</strong> de chaque pilote.
      </p>

      {/* Controls */}
      <div style={{ display:'flex', gap:'1rem', flexWrap:'wrap', alignItems:'flex-end', marginBottom:'1.5rem' }}>
        <div className="form-group">
          <label className="form-label">Saison</label>
          <select value={year} onChange={e => setYear(+e.target.value)}>
            {ALL_YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Grand Prix</label>
          <select value={circuit} onChange={e => { setCircuit(e.target.value); setIsSprint(false); setHasSprint(false) }}
            disabled={loadingRaces}>
            {loadingRaces
              ? <option>Chargement…</option>
              : races.map(r => <option key={r.round} value={r.raceName}>R{r.round} — {r.raceName}</option>)
            }
          </select>
        </div>
        {hasSprint && (
          <div className="form-group">
            <label className="form-label">Session</label>
            <select value={isSprint} onChange={e => setIsSprint(e.target.value === 'true')}>
              <option value="false">Course</option>
              <option value="true">Sprint</option>
            </select>
          </div>
        )}
        <button className="btn" onClick={loadSession} disabled={loading}>
          {loading ? `Chargement ${loadingDrv ?? ''}…` : '📈 Charger'}
        </button>
      </div>

      {error && <div className="error">Erreur : {error}</div>}

      {/* Positions chart */}
      {posData && (
        <>
          <div className="section-title">🏎️ Positions en course</div>
          <Plot data={posChart.data} layout={posChart.layout}
            config={PLOTLY_CONFIG} style={{ width:'100%' }} />
        </>
      )}

      {/* Telemetry pills + charts */}
      {drivers.length > 0 && (
        <>
          <div className="section-title" style={{ marginTop:'1.5rem' }}>📈 Télémétrie — Meilleur tour</div>
          <div className="pills">
            {drivers.map(drv => {
              const color = telData[drv]?.color ?? '#888'
              const active = selected.includes(drv)
              return (
                <span key={drv} className={`pill ${active ? 'active' : 'inactive'}`}
                  style={{ background:color+'22', color, borderColor:active ? color : 'transparent' }}
                  onClick={() => toggleDriver(drv)}>
                  {drv}
                </span>
              )
            })}
          </div>
        </>
      )}

      {activeTel.length > 0 && charts.map((chart, i) => (
        <Plot key={i} data={chart.data} layout={chart.layout}
          config={PLOTLY_CONFIG} style={{ width:'100%' }} />
      ))}

      {!loading && drivers.length === 0 && !error && (
        <div className="empty">
          <div className="empty-icon">📈</div>
          <div className="empty-text">Sélectionnez une saison et un GP puis cliquez sur Charger</div>
        </div>
      )}

      <p style={{ fontSize:'0.75rem', color:'var(--muted)', marginTop:'1.5rem', lineHeight:'1.6' }}>
        Données télémétriques fournies par{' '}
        <a href="https://theoehrly.github.io/Fast-F1/" target="_blank" rel="noreferrer"
          style={{ color:'var(--red)', textDecoration:'none' }}>FastF1</a>
        {' '}· Résultats historiques via{' '}
        <a href="https://api.jolpi.ca" target="_blank" rel="noreferrer"
          style={{ color:'var(--red)', textDecoration:'none' }}>Jolpica / Ergast</a>
        . Merci à eux ! 🙏
      </p>
    </div>
  )
}
