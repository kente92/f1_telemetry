import React, { useState, useEffect } from 'react'
import { apiFetch } from '../hooks/useApi'

const ALL_YEARS = Array.from(
  { length: new Date().getFullYear() - 1949 },
  (_, i) => new Date().getFullYear() - i
)

export default function ResultsPage() {
  const [year,        setYear]        = useState(ALL_YEARS[0])
  const [races,       setRaces]       = useState([])
  const [circuit,     setCircuit]     = useState('')   // raceName envoyé à FastF1
  const [data,        setData]        = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [loadingRaces,setLoadingRaces]= useState(false)
  const [error,       setError]       = useState(null)
  const [isSprint,    setIsSprint]    = useState(false)
  const [standings,   setStandings]   = useState(null)
  const [hasSprint,   setHasSprint]   = useState(false)

  useEffect(() => {
    setLoadingRaces(true)
    setData(null)
    setError(null)
    fetch('/api/gp-history')
      .then(r => r.json())
      .then(d => {
        const yr = (d.races || [])
          .filter(r => r.year === year)
          .sort((a, b) => a.round - b.round)
        setRaces(yr)
        if (yr.length > 0) setCircuit(yr[yr.length - 1].raceName)
        setIsSprint(false)
        setHasSprint(false)
        setLoadingRaces(false)
        // Load final standings for this year
        const lastRound = yr.length > 0 ? yr[yr.length - 1].round : 0
        const standingsYear = yr.length > 0 ? yr[0].year : year
        if (lastRound > 0) {
          // On demande les standings APRES le dernier round (round+1)
          // Si ca echoue (fin de saison), on retente avec le round exact
          fetch(`/api/standings/${standingsYear}/${lastRound + 1}`)
            .then(r => r.json())
            .then(s => {
              if (s.drivers?.length > 0) {
                setStandings(s)
              } else {
                // Fallback : standings du dernier round lui-meme
                return fetch(`/api/standings/${standingsYear}/${lastRound}`)
                  .then(r => r.json())
                  .then(s2 => setStandings(s2.drivers?.length > 0 ? s2 : null))
              }
            })
            .catch(() => setStandings(null))
        }
      })
      .catch(() => setLoadingRaces(false))
  }, [year])

  const load = async () => {
    if (!circuit) return
    setLoading(true); setError(null); setData(null)
    try {
      const url = isSprint ? `/api/sprint/${year}/${encodeURIComponent(circuit)}` : `/api/sessions/${year}/${encodeURIComponent(circuit)}`
      const d = await apiFetch(url)
      setData(d)
      // Check sprint availability separately
      if (!isSprint) {
        fetch(`/api/sprint/${year}/${encodeURIComponent(circuit)}`)
          .then(r => r.json())
          .then(s => setHasSprint(s.available || false))
          .catch(() => setHasSprint(false))
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const podium = data?.results?.slice(0, 3) ?? []
  const medals = ['🥇','🥈','🥉']

  return (
    <div>
      <h1 className="condensed" style={{ fontSize:'2rem', fontWeight:900,
        textTransform:'uppercase', marginBottom:'1.5rem',
        background:'linear-gradient(90deg,#e8002d,#ff6b6b,#fff)',
        WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>
        Résultats de la course
      </h1>

      <div style={{ display:'flex', gap:'1rem', flexWrap:'wrap', alignItems:'flex-end', marginBottom:'1.5rem' }}>
        <div className="form-group">
          <label className="form-label">Saison</label>
          <select value={year} onChange={e => setYear(+e.target.value)}>
            {ALL_YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Grand Prix</label>
          <select value={circuit} onChange={e => { setCircuit(e.target.value); setIsSprint(false); setHasSprint(false); setData(null) }}
            disabled={loadingRaces}>
            {loadingRaces
              ? <option>Chargement…</option>
              : races.length === 0
              ? <option>Aucun GP trouvé</option>
              : races.map(r => (
                  <option key={r.round} value={r.raceName}>
                    R{r.round} — {r.raceName}
                  </option>
                ))
            }
          </select>
        </div>
        {hasSprint && (
          <div className="form-group">
            <label className="form-label">Type</label>
            <select value={isSprint} onChange={e => { setIsSprint(e.target.value === 'true'); setData(null) }}>
              <option value="false">Course</option>
              <option value="true">Sprint</option>
            </select>
          </div>
        )}
        <button className="btn" onClick={load} disabled={loading || !circuit || loadingRaces}>
          {loading ? 'Chargement…' : '🏁 Charger'}
        </button>
      </div>



      {error   && <div className="error">Erreur : {error}</div>}
      {loading && <div className="loading">Téléchargement en cours…</div>}

      {data && (
        <>
          <div className="section-title">🏆 Podium — {circuit} {year}</div>
          <div className="grid-3" style={{ marginBottom:'1.5rem' }}>
            {podium.map((r, i) => (
              <div key={i} className="podium-card" style={{ '--driver-color': r.color }}>
                <div className="podium-medal">{medals[i]}</div>
                <div className="podium-abbr">{r.abbreviation}</div>
                <div className="podium-name">{r.fullName}</div>
                <div style={{ fontSize:'0.8rem', color: r.color, marginTop:'0.2rem',
                  fontFamily:'Barlow Condensed', fontWeight:600 }}>{r.team}</div>
                <div className="podium-laptime">{r.fastestLap ?? 'N/A'}</div>
              </div>
            ))}
          </div>

          <div className="section-title">📋 Résultats complets</div>
          <div style={{ overflowX:'auto' }}>
            <table className="results-table">
              <thead>
                <tr>
                  <th>Pos</th><th>Pilote</th><th>Écurie</th>
                  <th>Grille</th><th>Statut</th><th>Pts</th><th>Meilleur tour</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((r, i) => (
                  <tr key={i}>
                    <td><strong>{r.position ?? '—'}</strong></td>
                    <td>
                      <span className="driver-dot" style={{ background: r.color }} />
                      <strong>{r.abbreviation}</strong>
                      <span style={{ color:'var(--muted)', marginLeft:'0.4rem', fontSize:'0.8rem' }}>
                        {r.fullName}
                      </span>
                    </td>
                    <td style={{ color: r.color, fontSize:'0.85rem', fontWeight:600 }}>{r.team}</td>
                    <td style={{ textAlign:'center' }}>{r.grid ?? '—'}</td>
                    <td style={{ fontSize:'0.8rem',
                      color: r.status === 'Finished' ? 'var(--text)' : 'var(--muted)' }}>
                      {r.status}
                    </td>
                    <td style={{ textAlign:'center' }}>{r.points}</td>
                    <td style={{ fontFamily:'Barlow Condensed', fontSize:'0.95rem' }}>
                      {r.fastestLap ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <div className="empty">
          <div className="empty-icon">🏎️</div>
          <div className="empty-text">Sélectionnez une saison et un GP puis cliquez sur Charger</div>
        </div>
      )}

      {standings && standings.drivers?.length > 0 && (
        <>
          <div className="section-title" style={{ marginTop:'2rem' }}>
            🏆 Classement final {year} — Pilotes
          </div>
          <div style={{ overflowX:'auto', marginBottom:'1.5rem' }}>
            <table className="results-table">
              <thead>
                <tr><th>Pos</th><th>Pilote</th><th>Écurie</th><th>Pts</th><th>Victoires</th></tr>
              </thead>
              <tbody>
                {standings.drivers.map((d, i) => (
                  <tr key={i}>
                    <td><strong>{d.position}</strong></td>
                    <td>
                      <span className="driver-dot" style={{ background: d.color || '#888' }} />
                      <strong>{d.name}</strong>
                    </td>
                    <td style={{ color: d.color || 'var(--muted)', fontSize:'0.85rem', fontWeight:600 }}>{d.constructor}</td>
                    <td><strong style={{ color:'var(--red)' }}>{d.points}</strong></td>
                    <td>{d.wins}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="section-title">🏭 Classement final {year} — Écuries</div>
          <div style={{ overflowX:'auto', marginBottom:'2rem' }}>
            <table className="results-table">
              <thead>
                <tr><th>Pos</th><th>Écurie</th><th>Pts</th><th>Victoires</th></tr>
              </thead>
              <tbody>
                {standings.constructors.map((d, i) => (
                  <tr key={i}>
                    <td><strong>{d.position}</strong></td>
                    <td>
                      <span className="driver-dot" style={{ background: d.color || '#888' }} />
                      <strong style={{ color: d.color || 'var(--text)' }}>{d.name}</strong>
                    </td>
                    <td><strong style={{ color:'var(--red)' }}>{d.points}</strong></td>
                    <td>{d.wins}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p style={{ fontSize:'0.75rem', color:'var(--muted)', marginTop:'1.5rem', lineHeight:'1.6' }}>
        Données fournies par{' '}
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
