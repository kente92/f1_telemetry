import React, { useState, useEffect } from 'react'
import Plot from 'react-plotly.js'
import { PLOTLY_LAYOUT, PLOTLY_CONFIG } from '../constants'
import { apiFetch } from '../hooks/useApi'

const ALL_YEARS = Array.from(
  { length: new Date().getFullYear() - 2017 },
  (_, i) => new Date().getFullYear() - i
)

// Guide contextuel selon l'étape
const GUIDES = {
  before_quali: {
    icon: '📅',
    title: 'Avant les qualifications (jeudi/vendredi)',
    color: '#00d2ff',
    steps: [
      { ok: true,  text: 'Sélectionnez la saison et le Grand Prix' },
      { ok: true,  text: 'Le numéro de manche est automatique' },
      { ok: false, text: 'NE PAS cocher "Grille de départ" — les qualifs n\'ont pas eu lieu' },
      { ok: true,  text: 'Récupérez la météo si disponible' },
      { ok: true,  text: 'Cliquez Prédire → prédiction basée sur les standings du championnat' },
    ]
  },
  after_quali: {
    icon: '🏁',
    title: 'Après les qualifications (samedi soir)',
    color: '#FFD700',
    steps: [
      { ok: true,  text: 'Sélectionnez la saison et le Grand Prix' },
      { ok: true,  text: 'Cochez "Grille de départ"' },
      { ok: true,  text: 'Cliquez "Récupérer via Jolpica" pour charger la grille automatiquement' },
      { ok: true,  text: 'Récupérez la météo' },
      { ok: true,  text: 'Cliquez Prédire → prédiction la plus précise' },
    ]
  },
  race_day: {
    icon: '🏎️',
    title: 'Jour de course (dimanche)',
    color: '#e8002d',
    steps: [
      { ok: true,  text: 'Même procédure qu\'après les qualifs' },
      { ok: true,  text: 'Vérifiez la météo — elle peut avoir changé' },
      { ok: true,  text: 'Si pluie : cochez "Forcer pluie" pour simuler une course humide' },
      { ok: true,  text: 'La prédiction tient compte de la pluie dans le modèle ML' },
    ]
  },
}

export default function PredictPage() {
  const [year,       setYear]       = useState(ALL_YEARS[0])
  const [races,      setRaces]      = useState([])
  const [circuit,    setCircuit]    = useState('')
  const [round,      setRound]      = useState(1)
  const [raceDate,   setRaceDate]   = useState(null)
  const [loadingRaces, setLoadingRaces] = useState(false)
  const [useGrid,    setUseGrid]    = useState(false)
  const [rainfall,   setRainfall]   = useState(0)
  const [rainProb,   setRainProb]   = useState(null)
  const [gridMap,    setGridMap]    = useState({})
  const [gridData,   setGridData]   = useState([])
  const [manualGrid, setManualGrid] = useState(false)
  const [predictions,setPredictions]= useState(null)
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState(null)
  const [guide,      setGuide]      = useState('before_quali')

  // Charge la liste des GP quand l'année change
  useEffect(() => {
    setLoadingRaces(true)
    setCircuit('')
    setRound(1)
    setRaceDate(null)
    setPredictions(null)
    fetch(`/api/calendar/${year}`)
      .then(r => r.json())
      .then(d => {
        const yr = (d.races || []).sort((a, b) => a.round - b.round)
        setRaces(yr)
        if (yr.length > 0) {
          // Pré-sélectionne la prochaine course à venir (ou la dernière si saison terminée)
          const today = new Date()
          const next = yr.find(r => new Date(r.date) >= today) || yr[yr.length - 1]
          setCircuit(next.raceName)
          setRound(next.round)
          setRaceDate(next.date)
        }
        setLoadingRaces(false)
      })
      .catch(() => setLoadingRaces(false))
  }, [year])

  // Auto-détecte le numéro de manche quand le circuit change
  const handleCircuitChange = (raceName) => {
    setCircuit(raceName)
    setPredictions(null)
    setGridMap({})
    setRainfall(0)
    setRainProb(null)
    const found = races.find(r => r.raceName === raceName)
    if (found) {
      setRound(found.round)
      setRaceDate(found.date)
    }
  }

  const fetchWeather = async () => {
    try {
      const d = await apiFetch(`/api/weather/${encodeURIComponent(circuit)}`)
      setRainfall(d.rainfall)
      setRainProb(d.probability)
    } catch {}
  }

  const fetchGrid = async () => {
    try {
      const d = await apiFetch(`/api/qualifying/${year}/${round}`)
      if (d.grid?.length) {
        const m = {}
        d.grid.forEach(r => { m[r.driverId] = r.position })
        setGridMap(m)
        setGridData(d.grid)
        setManualGrid(false)
      } else {
        alert('Qualifications pas encore disponibles. Utilisez la saisie manuelle.')
        await loadManualGrid()
      }
    } catch (e) { setError(e.message) }
  }

  const loadManualGrid = async () => {
    setManualGrid(true)
    try {
      const s = await apiFetch(`/api/standings/${year}/${round}`)
      setGridData(s.drivers.map(d => ({ driverId: d.driverId, name: d.name, position: 0 })))
    } catch {}
  }

  const predict = async () => {
    setLoading(true); setError(null); setPredictions(null)
    try {
      const params = new URLSearchParams({
        year, round_num: round, circuit,
        use_grid: useGrid,
        rainfall,
        grid_json: JSON.stringify(gridMap),
      })
      const d = await apiFetch(`/api/predict?${params}`)
      setPredictions(d)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const top3  = predictions?.predictions?.slice(0, 3)  ?? []
  const all20 = predictions?.predictions              ?? []
  const medals = ['🥇','🥈','🥉']

  // Détermine le contexte temporel
  const today = new Date()
  const rDate = raceDate ? new Date(raceDate) : null
  const daysToRace = rDate ? Math.ceil((rDate - today) / (1000*60*60*24)) : null

  return (
    <div style={{ display:'flex', gap:'2rem', alignItems:'flex-start', flexWrap:'wrap' }}>

      {/* ── Colonne principale ─────────────────────────────────────────── */}
      <div style={{ flex:1, minWidth:0 }}>
        <h1 className="condensed" style={{ fontSize:'2rem', fontWeight:900,
          textTransform:'uppercase', marginBottom:'1.5rem',
          background:'linear-gradient(90deg,#e8002d,#ff6b6b,#fff)',
          WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>
          Prédictions
        </h1>

        {/* Paramètres */}
        <div className="section-title">Paramètres de la course</div>
        <div style={{ display:'flex', gap:'1rem', flexWrap:'wrap', alignItems:'flex-end', marginBottom:'1rem' }}>
          <div className="form-group">
            <label className="form-label">Saison</label>
            <select value={year} onChange={e => setYear(+e.target.value)}>
              {ALL_YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Grand Prix</label>
            <select value={circuit} onChange={e => handleCircuitChange(e.target.value)}
              disabled={loadingRaces}>
              {loadingRaces
                ? <option>Chargement…</option>
                : races.map(r => <option key={r.round} value={r.raceName}>
                    R{r.round} — {r.raceName}
                  </option>)
              }
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">N° manche</label>
            <input type="number" value={round} min={1} max={24}
              onChange={e => setRound(+e.target.value)}
              style={{ width:'70px' }} />
          </div>
        </div>

        {raceDate && (
          <p style={{ fontSize:'0.8rem', color:'var(--muted)', marginBottom:'1rem' }}>
            📅 Date de la course : <strong style={{ color:'var(--text)' }}>
              {new Date(raceDate).toLocaleDateString('fr-FR', { weekday:'long', day:'numeric', month:'long', year:'numeric' })}
            </strong>
            {daysToRace !== null && daysToRace > 0 && (
              <span style={{ marginLeft:'0.8rem', color:'var(--red)' }}>
                (dans {daysToRace} jour{daysToRace > 1 ? 's' : ''})
              </span>
            )}
            {daysToRace !== null && daysToRace <= 0 && (
              <span style={{ marginLeft:'0.8rem', color:'#00d2ff' }}>(course passée)</span>
            )}
          </p>
        )}

        {/* Météo */}
        <div className="section-title">🌦️ Météo</div>
        <div style={{ display:'flex', gap:'1rem', alignItems:'center', flexWrap:'wrap', marginBottom:'1rem' }}>
          <button className="btn btn-outline" onClick={fetchWeather}>
            Récupérer la météo
          </button>
          {rainProb !== null && (
            <span style={{ fontSize:'0.9rem' }}>
              {rainfall === 1
                ? <span style={{ color:'#00d2ff' }}>⛈️ Pluie probable ({rainProb}%)</span>
                : <span style={{ color:'#ffaa00' }}>☀️ Temps sec ({rainProb}% de pluie)</span>
              }
            </span>
          )}
          <label className="checkbox-row">
            <input type="checkbox" checked={rainfall === 1}
              onChange={e => setRainfall(e.target.checked ? 1 : 0)} />
            <span>Forcer pluie</span>
          </label>
        </div>

        {/* Grille */}
        <div className="section-title">🏁 Grille de départ</div>
        <div style={{ marginBottom:'1rem' }}>
          <label className="checkbox-row" style={{ marginBottom:'0.8rem' }}>
            <input type="checkbox" checked={useGrid}
              onChange={e => { setUseGrid(e.target.checked); if (!e.target.checked) { setGridMap({}); setManualGrid(false) } }} />
            <span>Tenir compte des positions de départ (après qualifications)</span>
          </label>

          {useGrid && (
            <div style={{ display:'flex', gap:'0.8rem', flexWrap:'wrap', alignItems:'center', marginTop:'0.5rem' }}>
              <button className="btn btn-outline" onClick={fetchGrid}>
                🔄 Récupérer automatiquement
              </button>
              <button className="btn btn-outline" onClick={loadManualGrid}>
                ✏️ Saisie manuelle
              </button>
              {Object.keys(gridMap).length > 0 && !manualGrid && (
                <span style={{ fontSize:'0.85rem', color:'#00d2ff' }}>
                  ✅ {Object.keys(gridMap).length} pilotes chargés
                </span>
              )}
            </div>
          )}

          {useGrid && manualGrid && gridData.length > 0 && (() => {
            const usedPositions = Object.values(gridMap).filter(v => v > 0)
            const hasDupes = usedPositions.length !== new Set(usedPositions).size
            return (
              <div style={{ marginTop:'0.8rem' }}>
                {hasDupes && (
                  <div style={{ background:'rgba(232,0,45,0.15)', border:'1px solid var(--red)',
                    borderRadius:'4px', padding:'0.5rem 0.8rem', marginBottom:'0.8rem',
                    fontSize:'0.8rem', color:'var(--red-light)' }}>
                    ⚠️ Certaines positions sont attribuées à plusieurs pilotes
                  </div>
                )}
                <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(220px,1fr))', gap:'0.4rem' }}>
                  {gridData.map(d => {
                    const pos = gridMap[d.driverId] || ''
                    const isDupe = pos > 0 && usedPositions.filter(v => v === pos).length > 1
                    return (
                      <div key={d.driverId} style={{
                        display:'flex', alignItems:'center', gap:'0.6rem',
                        background: isDupe ? 'rgba(232,0,45,0.1)' : 'var(--bg2)',
                        border: `1px solid ${isDupe ? 'var(--red)' : 'var(--border)'}`,
                        borderRadius:'4px', padding:'0.4rem 0.6rem',
                      }}>
                        <div style={{ flex:1 }}>
                          <div style={{ fontSize:'0.85rem', fontWeight:600, color:'var(--text)' }}>
                            {d.name.split(' ').pop()}
                          </div>
                          <div style={{ fontSize:'0.7rem', color:'var(--muted)' }}>
                            {d.name.split(' ').slice(0,-1).join(' ')}
                          </div>
                        </div>
                        <div style={{ display:'flex', alignItems:'center', gap:'0.3rem' }}>
                          <button onClick={() => setGridMap(prev => ({
                              ...prev, [d.driverId]: Math.max(0, (prev[d.driverId]||0) - 1)
                            }))}
                            style={{ background:'var(--bg3)', border:'1px solid var(--border)',
                              color:'var(--text)', width:'24px', height:'24px', borderRadius:'3px',
                              cursor:'pointer', fontSize:'1rem', lineHeight:1 }}>−</button>
                          <span style={{ fontFamily:'Barlow Condensed', fontWeight:700,
                            fontSize:'1.1rem', minWidth:'28px', textAlign:'center',
                            color: pos > 0 ? 'var(--text)' : 'var(--muted)' }}>
                            {pos || '—'}
                          </span>
                          <button onClick={() => setGridMap(prev => ({
                              ...prev, [d.driverId]: Math.min(20, (prev[d.driverId]||0) + 1)
                            }))}
                            style={{ background:'var(--bg3)', border:'1px solid var(--border)',
                              color:'var(--text)', width:'24px', height:'24px', borderRadius:'3px',
                              cursor:'pointer', fontSize:'1rem', lineHeight:1 }}>+</button>
                        </div>
                      </div>
                    )
                  })}
                </div>
                {(() => {
                  const assigned = Object.values(gridMap).filter(v => v > 0)
                  const allPositions = Array.from({length: 20}, (_, i) => i + 1)
                  const missing = allPositions.filter(p => !assigned.includes(p))
                  return (
                    <p style={{ fontSize:'0.75rem', color:'var(--muted)', marginTop:'0.5rem', lineHeight:'1.6' }}>
                      {assigned.length}/20 positions saisies
                      {hasDupes ? ' · ⚠️ doublons détectés' : ' · ✅ pas de doublon'}
                      {missing.length > 0 && missing.length <= 20 && (
                        <span style={{ display:'block', color:'var(--muted)' }}>
                          Positions non attribuées : <strong style={{ color:'var(--text)' }}>
                            {missing.join(', ')}
                          </strong>
                        </span>
                      )}
                    </p>
                  )
                })()}
              </div>
            )
          })()}
        </div>

        {/* Bouton */}
        <button className="btn" onClick={predict} disabled={loading}
          style={{ marginBottom:'2rem', minWidth:'200px' }}>
          {loading ? 'Calcul en cours…' : '🔮 Prédire'}
        </button>

        {error && <div className="error">Erreur : {error}</div>}

        {/* Résultats */}
        {predictions && (
          <>
            <p style={{ fontSize:'0.8rem', color:'var(--muted)', marginBottom:'1rem' }}>
              {circuit} · {year} · Manche {round}
              {useGrid ? ' · Avec grille' : ' · Sans grille'}
              {rainfall === 1 ? ' · ⛈️ Pluie' : ' · ☀️ Sec'}
              {' · '}Modèles : {predictions.models.join(', ')}
            </p>

            <div className="section-title">🏆 Podium prédit</div>
            <div className="grid-3" style={{ marginBottom:'1.5rem' }}>
              {top3.map((r, i) => (
                <div key={i} className="card card-red-left" style={{ borderLeftColor:'#ff6b35' }}>
                  <div style={{ fontFamily:'Barlow Condensed', fontWeight:900,
                    fontSize:'1.3rem', color:'#ff6b35' }}>
                    {medals[i]} {r.name.toUpperCase()}
                  </div>
                  <div style={{ fontSize:'0.75rem', color:'var(--muted)', textTransform:'uppercase', marginTop:'0.2rem' }}>
                    {r.constructor}{r.grid ? ` · Grille P${r.grid}` : ''}
                  </div>
                  <div style={{ fontFamily:'Barlow Condensed', fontSize:'1.4rem',
                    fontWeight:700, color:'white', marginTop:'0.4rem' }}>
                    {(r.proba_avg * 100).toFixed(1)}%
                    <span style={{ fontSize:'0.8rem', color:'var(--muted)', fontWeight:400 }}> prob. podium</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="section-title">Classement complet</div>
            <div style={{ maxWidth:'600px', marginBottom:'2rem' }}>
              {all20.map((r, i) => {
                const pct   = (r.proba_avg * 100).toFixed(1)
                const hl    = i < 6
                const color = hl ? '#e8002d' : 'var(--border)'
                return (
                  <div key={i} style={{ display:'flex', alignItems:'center', gap:'0.8rem',
                    background: hl ? 'var(--bg3)' : 'var(--bg2)',
                    borderLeft:`3px solid ${color}`, borderRadius:'4px',
                    padding:'0.5rem 0.8rem', marginBottom:'0.3rem' }}>
                    <div style={{ fontFamily:'Barlow Condensed', fontWeight:700,
                      fontSize:'1.1rem', minWidth:'2rem', textAlign:'right',
                      color: hl ? 'white' : 'var(--muted)' }}>{r.position}</div>
                    <div style={{ flex:1 }}>
                      <div style={{ fontFamily:'Barlow Condensed', fontWeight:600,
                        fontSize:'0.95rem', color: hl ? 'white' : '#aaa' }}>{r.name}</div>
                      <div style={{ fontSize:'0.7rem', color:'var(--muted)', textTransform:'uppercase' }}>
                        {r.constructor}{r.grid ? ` · P${r.grid}` : ''}
                      </div>
                    </div>
                    <div style={{ textAlign:'right', minWidth:'3.5rem' }}>
                      <div style={{ fontFamily:'Barlow Condensed', fontWeight:700,
                        color: hl ? color : 'var(--muted)' }}>{pct}%</div>
                      <div style={{ background:'var(--border)', borderRadius:'2px',
                        height:'3px', marginTop:'2px' }}>
                        <div style={{ height:'3px', borderRadius:'2px',
                          width:`${Math.round(r.proba_avg*120)}px`, maxWidth:'100%',
                          background: hl ? color : '#333' }} />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Graphique probabilités */}
            <div className="section-title">Probabilités par modèle</div>
            <Plot
              data={[
                { x:all20.map(r=>r.name.split(' ').pop()), y:all20.map(r=>+(r.proba_rf*100).toFixed(1)),
                  name:'Random Forest', type:'bar', marker:{color:'#e8002d',opacity:0.85} },
                { x:all20.map(r=>r.name.split(' ').pop()), y:all20.map(r=>+(r.proba_dt*100).toFixed(1)),
                  name:'Decision Tree', type:'bar', marker:{color:'#00d2ff',opacity:0.85} },
                ...(all20[0]?.proba_svc !== undefined ? [{
                  x:all20.map(r=>r.name.split(' ').pop()), y:all20.map(r=>+(r.proba_svc*100).toFixed(1)),
                  name:'SVC', type:'bar', marker:{color:'#00ff88',opacity:0.85}
                }] : []),
              ]}
              layout={{ ...PLOTLY_LAYOUT, height:280, barmode:'group',
                xaxis:{...PLOTLY_LAYOUT.xaxis,tickangle:-45,tickfont:{color:'#888',size:9}},
                yaxis:{...PLOTLY_LAYOUT.yaxis,title:{text:'P(podium) %',font:{color:'#888',size:10}}},
              }}
              config={PLOTLY_CONFIG} style={{ width:'100%' }}
            />
          </>
        )}

        {!predictions && !loading && !error && (
          <div className="empty">
            <div className="empty-icon">🔮</div>
            <div className="empty-text">Configurez la course et cliquez sur Prédire</div>
          </div>
        )}

        <p style={{ fontSize:'0.75rem', color:'var(--muted)', marginTop:'1.5rem', lineHeight:'1.6' }}>
          Modèles ML : Random Forest · Decision Tree · SVC avec RandomOverSampler ·{' '}
          Données via{' '}
          <a href="https://api.jolpi.ca" target="_blank" rel="noreferrer"
            style={{ color:'var(--red)', textDecoration:'none' }}>Jolpica / Ergast</a>
          {' '}· Météo via{' '}
          <a href="https://open-meteo.com" target="_blank" rel="noreferrer"
            style={{ color:'var(--red)', textDecoration:'none' }}>Open-Meteo</a>
          . Merci à eux ! 🙏
        </p>
      </div>

      {/* ── Colonne guide ──────────────────────────────────────────────── */}
      <div style={{ width:'280px', flexShrink:0, minWidth:'280px', flex:'1' }}>
        <div className="section-title">📖 Guide d'utilisation</div>

        {/* Sélecteur de contexte */}
        <div style={{ display:'flex', flexDirection:'column', gap:'0.4rem', marginBottom:'1rem' }}>
          {Object.entries(GUIDES).map(([key, g]) => (
            <button key={key}
              onClick={() => setGuide(key)}
              style={{
                background: guide === key ? g.color + '22' : 'var(--bg2)',
                border: `1px solid ${guide === key ? g.color : 'var(--border)'}`,
                color: guide === key ? g.color : 'var(--muted)',
                borderRadius:'4px', padding:'0.5rem 0.8rem',
                fontFamily:'Barlow Condensed', fontWeight:600,
                fontSize:'0.85rem', cursor:'pointer', textAlign:'left',
                transition:'all 0.15s',
              }}>
              {g.icon} {g.title}
            </button>
          ))}
        </div>

        {/* Contenu du guide */}
        {(() => {
          const g = GUIDES[guide]
          return (
            <div className="card" style={{ borderLeft:`3px solid ${g.color}` }}>
              <div style={{ fontFamily:'Barlow Condensed', fontWeight:700,
                fontSize:'1rem', color: g.color, marginBottom:'0.8rem' }}>
                {g.icon} {g.title}
              </div>
              {g.steps.map((step, i) => (
                <div key={i} style={{ display:'flex', gap:'0.5rem',
                  marginBottom:'0.5rem', alignItems:'flex-start' }}>
                  <span style={{ fontSize:'0.9rem', flexShrink:0 }}>
                    {step.ok ? '✅' : '❌'}
                  </span>
                  <span style={{ fontSize:'0.8rem', color:'var(--text)', lineHeight:'1.4' }}>
                    {step.text}
                  </span>
                </div>
              ))}
            </div>
          )
        })()}

        {/* Explication du N° de manche */}
        <div className="card" style={{ marginTop:'1rem', borderLeft:'3px solid var(--border)' }}>
          <div style={{ fontFamily:'Barlow Condensed', fontWeight:700,
            fontSize:'0.9rem', color:'var(--muted)', marginBottom:'0.5rem' }}>
            ℹ️ À quoi servent ces champs ?
          </div>
          <p style={{ fontSize:'0.78rem', color:'var(--muted)', lineHeight:'1.5', marginBottom:'0.5rem' }}>
            <strong style={{ color:'var(--text)' }}>Grand Prix</strong> : détermine le circuit.
            Le modèle n'utilise pas le circuit directement mais les standings du championnat
            à ce stade de la saison.
          </p>
          <p style={{ fontSize:'0.78rem', color:'var(--muted)', lineHeight:'1.5', marginBottom:'0.5rem' }}>
            <strong style={{ color:'var(--text)' }}>N° de manche</strong> : automatiquement
            déduit du GP sélectionné. Permet de récupérer les standings après la manche précédente
            (ex: manche 5 → standings après la manche 4).
          </p>
          <p style={{ fontSize:'0.78rem', color:'var(--muted)', lineHeight:'1.5' }}>
            <strong style={{ color:'var(--text)' }}>Sans grille</strong> : prédiction disponible
            dès le jeudi. <strong style={{ color:'var(--text)' }}>Avec grille</strong> : plus
            précise, disponible après les qualifications du samedi.
          </p>
        </div>
      </div>

    </div>
  )
}
