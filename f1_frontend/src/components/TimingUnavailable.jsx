// components/TimingUnavailable.jsx — Message affiché quand l'API renvoie 503
// "timing_unavailable" (aucune donnée) ou "timing_incomplete" (archive partielle)

import React from 'react'

export const TIMING_UNAVAILABLE = 'timing_unavailable'
export const TIMING_INCOMPLETE  = 'timing_incomplete'

export const isTimingUnavailable = (err) =>
  err?.code === TIMING_UNAVAILABLE || err?.code === TIMING_INCOMPLETE

export default function TimingUnavailable({ code = TIMING_UNAVAILABLE }) {
  if (code === TIMING_INCOMPLETE) {
    return (
      <div className="error" style={{ marginTop:'1rem', lineHeight:'1.6' }}>
        <strong>Télémétrie incomplète pour cette course.</strong>{' '}
        Les données de chronométrage disponibles pour ce Grand Prix ne couvrent qu'une partie
        des tours : plutôt que d'afficher des graphes faussés, ce site préfère ne pas les montrer.
        Résultats, classements et prédictions restent disponibles.
      </div>
    )
  }
  return (
    <div className="error" style={{ marginTop:'1rem', lineHeight:'1.6' }}>
      <strong>Télémétrie indisponible pour cette course.</strong>{' '}
      Depuis octobre 2026, la F1 réserve l'accès à son archive de chronométrage aux abonnés F1TV,
      et ce site n'a pas pu la récupérer. Résultats, classements et prédictions restent disponibles.
      Les courses déjà archivées ici continuent de s'afficher.
    </div>
  )
}
