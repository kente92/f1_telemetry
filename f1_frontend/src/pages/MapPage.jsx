import React, { useState, useEffect } from 'react'
import Plot from 'react-plotly.js'
import { PLOTLY_CONFIG } from '../constants'

const PROJECTIONS = ['natural earth','mercator','orthographic','equirectangular','robinson','mollweide']
const MIN_YEAR = 1950
const MAX_YEAR = new Date().getFullYear()

function RangeSlider({ min, max, value, onChange }) {
  const [from, to] = value
  const pct = v => ((v - min) / (max - min)) * 100
  const fromPct = pct(from)
  const toPct   = pct(to)
  // Borne basse (from) toujours au-dessus par défaut pour faciliter la sélection
  const fromZ = 5
  const toZ   = 4

  return (
    <div style={{ position:'relative', height:'48px', userSelect:'none' }}>
      <div style={{ position:'absolute', top:'22px', left:0, right:0, height:'4px',
        background:'var(--border)', borderRadius:'2px' }} />
      <div style={{ position:'absolute', top:'22px', height:'4px', borderRadius:'2px',
        background:'var(--red)', left:`${fromPct}%`, right:`${100-toPct}%` }} />
      <input type="range" min={min} max={max} value={from}
        onChange={e => { const v=+e.target.value; if(v < to) onChange([v, to]) }}
        style={{ position:'absolute', width:'100%', height:'48px', top:0,
          appearance:'none', WebkitAppearance:'none', background:'transparent',
          outline:'none', cursor:'pointer', zIndex:fromZ }} />
      <input type="range" min={min} max={max} value={to}
        onChange={e => { const v=+e.target.value; if(v > from) onChange([from, v]) }}
        style={{ position:'absolute', width:'100%', height:'48px', top:0,
          appearance:'none', WebkitAppearance:'none', background:'transparent',
          outline:'none', cursor:'pointer', zIndex:toZ }} />
    </div>
  )
}


export default function MapPage() {
  const [races,      setRaces]      = useState([])
  const [loading,    setLoading]    = useState(true)
  const [yearRange,  setYearRange]  = useState([MIN_YEAR, MAX_YEAR])
  const [projection, setProjection] = useState('natural earth')
  const [bdayDay,    setBdayDay]    = useState('')
  const [bdayMonth,  setBdayMonth]  = useState('')
  const [bdayRaces,  setBdayRaces]  = useState(null)

  useEffect(() => {
    fetch('/api/gp-history')
      .then(r => r.json())
      .then(d => {
        setRaces((d.races || []).filter(r => r.lat !== null && r.lat !== undefined && r.lng !== null && r.lng !== undefined))
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const filtered = races.filter(r => r.year >= yearRange[0] && r.year <= yearRange[1])

  const searchBday = () => {
    const day   = parseInt(bdayDay)
    const month = parseInt(bdayMonth)
    if (!day || !month || day < 1 || day > 31 || month < 1 || month > 12) return
    const found = races.filter(r => {
      if (!r.date) return false
      const parts = String(r.date).split('-')
      if (parts.length < 3) return false
      return parseInt(parts[1]) === month && parseInt(parts[2]) === day
    }).sort((a, b) => a.year - b.year)
    setBdayRaces(found)
  }

  if (loading) return <div className="loading">Chargement de l'historique F1…</div>

  return (
    <div>
      {/* Slider CSS fix */}
      <style>{`
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 18px; height: 18px;
          border-radius: 50%;
          background: var(--red);
          border: 2px solid white;
          cursor: pointer;
          position: relative;
          z-index: 4;
        }
        input[type=range]::-moz-range-thumb {
          width: 18px; height: 18px;
          border-radius: 50%;
          background: var(--red);
          border: 2px solid white;
          cursor: pointer;
        }
      `}</style>

      <h1 className="condensed" style={{ fontSize:'2rem', fontWeight:900, textTransform:'uppercase',
        marginBottom:'1.5rem', background:'linear-gradient(90deg,#e8002d,#ff6b6b,#fff)',
        WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>
        Carte &amp; Dates des GP de F1
      </h1>

      <div className="section-title">Carte mondiale des circuits</div>

      <div style={{ display:'flex', gap:'1.5rem', flexWrap:'wrap', marginBottom:'1rem', alignItems:'flex-end' }}>
        <div className="form-group" style={{ flex:'1', minWidth:'300px' }}>
          <label className="form-label">
            Années : <strong style={{ color:'var(--text)' }}>{yearRange[0]}</strong>
            {' → '}
            <strong style={{ color:'var(--text)' }}>{yearRange[1]}</strong>
            <span style={{ color:'var(--muted)', marginLeft:'0.5rem' }}>({filtered.length} GP)</span>
          </label>
          <RangeSlider min={MIN_YEAR} max={MAX_YEAR} value={yearRange} onChange={setYearRange} />
          <div style={{ display:'flex', gap:'0.4rem', marginTop:'0.3rem', flexWrap:'wrap' }}>
            {[[1950,MAX_YEAR],[1980,MAX_YEAR],[2000,MAX_YEAR],[2010,MAX_YEAR],[2020,MAX_YEAR]].map(([a,b]) => (
              <button key={a} className="btn btn-outline"
                style={{ padding:'0.2rem 0.6rem', fontSize:'0.75rem' }}
                onClick={() => setYearRange([a, b])}>
                {a}+
              </button>
            ))}
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Projection</label>
          <select value={projection} onChange={e => setProjection(e.target.value)}>
            {PROJECTIONS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>

      <Plot
        data={[{
          type:'scattergeo', lat:filtered.map(r=>r.lat), lon:filtered.map(r=>r.lng),
          text:filtered.map(r=>`${r.raceName} ${r.year}`),
          customdata:filtered.map(r=>[r.country,r.location]),
          hovertemplate:'<b>%{text}</b><br>%{customdata[1]}, %{customdata[0]}<extra></extra>',
          mode:'markers',
          marker:{ size:5, color:filtered.map(r=>r.year),
            colorscale:[[0,'#1a0a00'],[0.5,'#e8002d'],[1,'#00d2ff']],
            colorbar:{title:'Année',tickfont:{color:'#888',size:9},thickness:10},
            showscale:true },
        }]}
        layout={{ height:480, paper_bgcolor:'#0a0a0f',
          geo:{ projection:{type:projection}, showland:true, landcolor:'#1a1a2e',
            showocean:true, oceancolor:'#0a0a0f', showcountries:true,
            countrycolor:'#2a2a3a', showframe:false, bgcolor:'#0a0a0f' },
          font:{family:'Barlow Condensed',color:'#888'},
          margin:{l:0,r:0,t:10,b:0} }}
        config={PLOTLY_CONFIG} style={{ width:'100%' }}
      />
      <p style={{ fontSize:'0.8rem', color:'var(--muted)', marginTop:'0.4rem' }}>
        <strong style={{color:'var(--text)'}}>{filtered.length.toLocaleString()}</strong> GP ·{' '}
        <strong style={{color:'var(--text)'}}>{new Set(filtered.map(r=>r.circuitName)).size}</strong> circuits
      </p>

      {/* Birthday */}
      <div className="section-title">🎂 Course le jour de ton anniversaire</div>
      <p style={{ fontSize:'0.85rem', color:'var(--muted)', marginBottom:'0.8rem' }}>
        Entrez votre jour et mois de naissance pour trouver les GP disputés ce jour-là.
      </p>
      <div style={{ display:'flex', gap:'0.8rem', alignItems:'flex-end', flexWrap:'wrap', marginBottom:'1rem' }}>
        <div className="form-group">
          <label className="form-label">Jour (1-31)</label>
          <input type="number" min={1} max={31}
            value={bdayDay} placeholder="ex: 15"
            onChange={e => setBdayDay(e.target.value)}
            style={{ width:'80px' }} />
        </div>
        <div className="form-group">
          <label className="form-label">Mois (1-12)</label>
          <input type="number" min={1} max={12}
            value={bdayMonth} placeholder="ex: 6"
            onChange={e => setBdayMonth(e.target.value)}
            style={{ width:'80px' }} />
        </div>
        <button className="btn" onClick={searchBday}
          disabled={!bdayDay || !bdayMonth}
          style={{ opacity: (!bdayDay || !bdayMonth) ? 0.5 : 1 }}>
          🎂 Chercher
        </button>
      </div>

      {bdayRaces !== null && (
        bdayRaces.length > 0 ? (
          <>
            <p style={{ marginBottom:'0.8rem', fontSize:'0.9rem' }}>
              <strong style={{color:'var(--red)'}}>{bdayRaces.length}</strong> course(s) un {bdayDay}/{bdayMonth} !
            </p>
            <table className="results-table" style={{ marginBottom:'1.5rem' }}>
              <thead><tr><th>Année</th><th>Grand Prix</th><th>Circuit</th><th>Ville</th><th>Pays</th></tr></thead>
              <tbody>
                {bdayRaces.map((r,i) => (
                  <tr key={i}>
                    <td><strong>{r.year}</strong></td>
                    <td>{r.raceName}</td>
                    <td>{r.circuitName}</td>
                    <td>{r.location}</td>
                    <td>{r.country}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Plot
              data={[{ type:'scattergeo', lat:bdayRaces.map(r=>r.lat), lon:bdayRaces.map(r=>r.lng),
                text:bdayRaces.map(r=>`${r.raceName} ${r.year}`),
                mode:'markers+text', textposition:'top center',
                textfont:{color:'#e8002d',size:9,family:'Barlow Condensed'},
                marker:{size:10,color:'#e8002d',line:{color:'white',width:1}},
                hovertemplate:'<b>%{text}</b><extra></extra>' }]}
              layout={{ height:320, paper_bgcolor:'#0a0a0f',
                geo:{projection:{type:'natural earth'},showland:true,landcolor:'#1a1a2e',
                  showocean:true,oceancolor:'#0a0a0f',showcountries:true,
                  countrycolor:'#2a2a3a',showframe:false,bgcolor:'#0a0a0f'},
                font:{family:'Barlow Condensed',color:'#888'},
                margin:{l:0,r:0,t:10,b:0} }}
              config={PLOTLY_CONFIG} style={{ width:'100%' }}
            />
          </>
        ) : (
          <p style={{ color:'var(--muted)', fontSize:'0.9rem' }}>
            Aucune course n'a eu lieu le {bdayDay}/{bdayMonth} dans l'histoire de la F1.
          </p>
        )
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