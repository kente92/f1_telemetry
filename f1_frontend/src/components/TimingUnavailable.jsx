// components/TimingUnavailable.jsx — Message affiché quand l'API renvoie 503 "timing_unavailable"

import React from 'react'

export const TIMING_UNAVAILABLE = 'timing_unavailable'

export const isTimingUnavailable = (err) => err?.code === TIMING_UNAVAILABLE

export default function TimingUnavailable() {
  return (
    <div className="error" style={{ marginTop:'1rem', lineHeight:'1.6' }}>
      <strong>Télémétrie indisponible pour cette course.</strong>{' '}
      Depuis octobre 2026, la F1 réserve l'accès à son archive de chronométrage aux abonnés F1TV,
      et ce site n'a pas pu la récupérer. Résultats, classements et prédictions restent disponibles.
      Les courses déjà archivées ici continuent de s'afficher.
    </div>
  )
}
