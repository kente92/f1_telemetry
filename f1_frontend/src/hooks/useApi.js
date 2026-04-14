// hooks/useApi.js — Generic fetch hook with loading/error states

import { useState, useEffect, useCallback } from 'react'

export function useApi(url, deps = []) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const fetch_ = useCallback(async () => {
    if (!url) return
    setLoading(true)
    setError(null)
    try {
      const r = await fetch(url)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setData(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [url])

  useEffect(() => { fetch_() }, [fetch_, ...deps])

  return { data, loading, error, refetch: fetch_ }
}

export async function apiFetch(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`)
  return r.json()
}
