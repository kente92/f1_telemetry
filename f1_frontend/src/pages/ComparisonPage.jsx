import React, { useState, useEffect } from 'react'
import Plot from 'react-plotly.js'
import { CIRCUITS, YEARS, PLOTLY_LAYOUT, PLOTLY_CONFIG } from '../constants'
import { apiFetch } from '../hooks/useApi'

export default function ComparisonPage() {
  const [year,    setYear]    = useState(YEARS[0])
  const [circuit, setCircuit] = useState('')
  const [races,   setRaces]   = useState([])
  const [loadingRaces, setLoadingRaces] = useState(false)
  const [drivers, setDrivers] = useState([])
  const [d1,      setD1]      = useState('')
  const [d2,      setD2]      = useState('')
  const [tel1,    setTel1]    = useState(null)
  const [tel2,    setTel2]    = useState(null)
  const [laps,    setLaps]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [isSprint,  setIsSprint]  = useState(false)
  const [hasSprint, setHasSprint] = useState(false)
  const [error,   setError]   = useState(null)
  useEffect(() => {
    setLoadingRaces(true)
    setCircuit('')
    fetch('/api/gp-history')
      .then(r => r.json())
      .then(d => {
        const yr = (d.races || []).filter(r => r.year === year).sort((a, b) => a.round - b.round)
        setRaces(yr)
        if (yr.length > 0) setCircuit(yr[yr.length - 1].raceName)
        setIsSprint(false)
        setHasSprint(false)
        setLoadingRaces(false)
      })
      .catch(() => setLoadingRaces(false))
  }, [year])

  const loadSession = async () => {
    setLoading(true); setError(null)
    setTel1(null); setTel2(null); setLaps(null); setDrivers([])
    try {
      const sess = await apiFetch(`/api/sessions/${year}/${encodeURIComponent(circuit)}`)
      setDrivers(sess.drivers || [])
      // Check sprint availability
      fetch(`/api/sprint/${year}/${encodeURIComponent(circuit)}`)
        .then(r => r.json()).then(s => setHasSprint(s.available || false))
        .catch(() => setHasSprint(false))
      if (sess.drivers?.length >= 2) {
        setD1(sess.drivers[0])
        setD2(sess.drivers[1])
      }
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const compare = async () => {
    if (!d1 || !d2 || d1 === d2) return
    setLoading(true); setError(null)
    try {
      const [t1, t2, lapData] = await Promise.all([
        apiFetch(`/api/telemetry/${year}/${encodeURIComponent(circuit)}/${d1}?sprint=${isSprint}`),
        apiFetch(`/api/telemetry/${year}/${encodeURIComponent(circuit)}/${d2}?sprint=${isSprint}`),
        apiFetch(`/api/laps/${year}/${encodeURIComponent(circuit)}/${d1}/${d2}?sprint=${isSprint}`),
      ])
      setTel1(t1); setTel2(t2); setLaps(lapData)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  // Delta map
  const makeDeltaMap = () => {
    if (!tel1?.x?.length || !tel2?.x?.length) return null
    const n = Math.min(tel1.distance.length, tel2.distance.length)
    const dist1 = tel1.distance.slice(0, n)
    const spd2i = tel1.distance.slice(0, n).map(d => {
      const idx = tel2.distance.findIndex(v => v >= d)
      return idx >= 0 ? tel2.speed[idx] : tel2.speed[tel2.speed.length - 1]
    })
    const delta = tel1.speed.slice(0, n).map((s, i) => s - spd2i[i])
    const dmax  = Math.max(...delta.map(Math.abs)) || 1

    return {
      data: [
        { x: tel1.x, y: tel1.y, type: 'scatter', mode: 'lines',
          line: { color: '#2a2a3a', width: 8 }, hoverinfo: 'skip', showlegend: false },
        { x: tel1.x.slice(0, n), y: tel1.y.slice(0, n),
          type: 'scatter', mode: 'markers',
          marker: {
            color: delta,
            colorscale: [[0, tel2.color],[0.5,'#1e1e2e'],[1, tel1.color]],
            size: 4, cmin: -dmax, cmax: dmax,
            colorbar: { title: 'Δ km/h', tickfont: { color:'#888',size:8 }, thickness:10,len:0.7 },
            showscale: true,
          },
          name: 'Δ vitesse',
          hovertemplate: 'Δ %{marker.color:.1f} km/h<extra></extra>' },
      ],
      layout: {
        ...PLOTLY_LAYOUT,
        height: 400,
        title: { text: `CARTE CIRCUIT — ${d1} vs ${d2}`, font: { family:'Barlow Condensed',size:12,color:'#e8002d' } },
        xaxis: { visible: false, scaleanchor: 'y', scaleratio: 1 },
        yaxis: { visible: false },
        margin: { l:10, r:60, t:50, b:10 },
      }
    }
  }

  // Lap times chart
  const makeLapChart = () => {
    if (!laps) return null
    const { driver1, driver2, sc_laps = [], vsc_laps = [] } = laps

    // SC/VSC vertical lines via shapes
    const shapes = [
      ...sc_laps.map(lap => ({
        type: 'line', x0: lap, x1: lap, y0: 0, y1: 1, yref: 'paper',
        line: { color: 'rgba(255,210,0,0.35)', width: 16 },
      })),
      ...vsc_laps.map(lap => ({
        type: 'line', x0: lap, x1: lap, y0: 0, y1: 1, yref: 'paper',
        line: { color: 'rgba(255,150,0,0.25)', width: 16 },
      })),
    ]

    return {
      data: [
        // SC/VSC legend entries
        ...(sc_laps.length ? [{
          x: [null], y: [null], name: '🟡 Safety Car', type: 'scatter', mode: 'lines',
          line: { color: 'rgba(255,210,0,0.7)', width: 10 }, showlegend: true,
        }] : []),
        ...(vsc_laps.length ? [{
          x: [null], y: [null], name: '🟠 VSC', type: 'scatter', mode: 'lines',
          line: { color: 'rgba(255,150,0,0.6)', width: 10 }, showlegend: true,
        }] : []),
        { x: driver1.laps, y: driver1.times, name: d1, type: 'scatter', mode: 'lines',
          line: { color: driver1.color, width: 2, dash: tel1?.dash || 'solid' },
          hovertemplate: `<b>${d1}</b> T%{x} — %{y:.3f}s<extra></extra>` },
        { x: driver2.laps, y: driver2.times, name: d2, type: 'scatter', mode: 'lines',
          line: { color: driver2.color, width: 2, dash: tel2?.dash || 'dot' },
          hovertemplate: `<b>${d2}</b> T%{x} — %{y:.3f}s<extra></extra>` },
        ...(driver1.pits.length ? [{
          x: driver1.pits,
          y: driver1.pits.map(p => driver1.times[driver1.laps.indexOf(p)]),
          name: `${d1} — Arrêt stands`, type: 'scatter', mode: 'markers',
          marker: { color: driver1.color, size: 10, symbol: 'triangle-up', line: { color:'white',width:1 } },
        }] : []),
        ...(driver2.pits.length ? [{
          x: driver2.pits,
          y: driver2.pits.map(p => driver2.times[driver2.laps.indexOf(p)]),
          name: `${d2} — Arrêt stands`, type: 'scatter', mode: 'markers',
          marker: { color: driver2.color, size: 10, symbol: 'triangle-up', line: { color:'white',width:1 } },
        }] : []),
      ],
      layout: {
        ...PLOTLY_LAYOUT,
        height: 340,
        shapes,
        title: { text: 'CHRONOS TOUR PAR TOUR', font: { family:'Barlow Condensed',size:12,color:'#e8002d' } },
        xaxis: { ...PLOTLY_LAYOUT.xaxis, title: { text:'Tour', font:{color:'#888',size:10} } },
        yaxis: { ...PLOTLY_LAYOUT.yaxis, title: { text:'Temps (s)', font:{color:'#888',size:10} } },
      }
    }
  }

  const deltaMap  = makeDeltaMap()
  const lapChart  = makeLapChart()

  return (
    <div>
      <h1 className="condensed" style={{ fontSize:'2rem', fontWeight:900,
        textTransform:'uppercase', marginBottom:'1.5rem',
        background:'linear-gradient(90deg,#e8002d,#ff6b6b,#fff)',
        WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>
        Comparaison des pilotes
      </h1>

      {/* Step 1: load session */}
      <div style={{ display:'flex', gap:'1rem', flexWrap:'wrap', alignItems:'flex-end', marginBottom:'1rem' }}>
        <div className="form-group">
          <label className="form-label">Saison</label>
          <select value={year} onChange={e => setYear(+e.target.value)}>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Grand Prix</label>
          <select value={circuit} onChange={e => { setCircuit(e.target.value); setIsSprint(false); setHasSprint(false) }} disabled={loadingRaces}>
            {loadingRaces
              ? <option>Chargement…</option>
              : races.map(r => <option key={r.round} value={r.raceName}>R{r.round} — {r.raceName}</option>)
            }
          </select>
        </div>
        <button className="btn btn-outline" onClick={loadSession} disabled={loading}>
          Charger les pilotes
        </button>
      </div>

      {/* Step 2: pick drivers */}
      {drivers.length > 0 && (
        <div style={{ display:'flex', gap:'1rem', flexWrap:'wrap', alignItems:'flex-end', marginBottom:'1.5rem' }}>
          <div className="form-group">
            <label className="form-label">Pilote 1</label>
            <select value={d1} onChange={e => setD1(e.target.value)}>
              {drivers.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Pilote 2</label>
            <select value={d2} onChange={e => setD2(e.target.value)}>
              {drivers.filter(d => d !== d1).map(d => <option key={d} value={d}>{d}</option>)}
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
          <button className="btn" onClick={compare} disabled={loading || !d1 || !d2 || d1 === d2}>
            {loading ? 'Chargement…' : '🗺️ Comparer'}
          </button>
        </div>
      )}

      {error && <div className="error">Erreur : {error}</div>}
      {loading && <div className="loading">Chargement des données de comparaison…</div>}

      {deltaMap && (
        <>
          <div className="section-title">🗺️ Carte du circuit — Delta vitesse</div>
          <p style={{ fontSize:'0.8rem', color:'var(--muted)', marginBottom:'0.5rem' }}>
            <span style={{ color: tel1?.color }}>■ {d1} plus rapide</span>
            {' · '}
            <span style={{ color: tel2?.color }}>■ {d2} plus rapide</span>
          </p>
          <Plot data={deltaMap.data} layout={deltaMap.layout}
            config={PLOTLY_CONFIG} style={{ width:'100%' }} />
        </>
      )}

      {lapChart && (
        <>
          <div className="section-title">⏱️ Chronos tour par tour</div>
          <p style={{ fontSize:'0.8rem', color:'var(--muted)', marginBottom:'0.5rem' }}>
            Les triangles ▲ indiquent les tours de sortie des stands.
          </p>
          <Plot data={lapChart.data} layout={lapChart.layout}
            config={PLOTLY_CONFIG} style={{ width:'100%' }} />
        </>
      )}

      {!loading && !drivers.length && !error && (
        <div className="empty">
          <div className="empty-icon">🗺️</div>
          <div className="empty-text">Chargez une course puis sélectionnez deux pilotes</div>
        </div>
      )}

            <p style={{ fontSize:'0.75rem', color:'var(--muted)', marginTop:'0.5rem', lineHeight:'1.6' }}>
        Données télémétriques fournies par{' '}
        <a href="https://theoehrly.github.io/Fast-F1/" target="_blank" rel="noreferrer"
          style={{ color:'var(--red)', textDecoration:'none' }}>FastF1</a>
        {' '}· Résultats historiques via{' '}
        <a href="https://api.jolpi.ca" target="_blank" rel="noreferrer"
          style={{ color:'var(--red)', textDecoration:'none' }}>Jolpica / Ergast</a>
        {' '}· Météo via{' '}
        <a href="https://open-meteo.com" target="_blank" rel="noreferrer"
          style={{ color:'var(--red)', textDecoration:'none' }}>Open-Meteo</a>
        . Merci à eux ! 🙏
      </p>
    </div>
  )
}
