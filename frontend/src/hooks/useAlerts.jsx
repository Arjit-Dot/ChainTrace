import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { alertStreamUrl, getAlerts } from '../lib/api'

// One EventSource for the whole app (/api/alerts/stream, event "alert"). The bell, the toasts and any page that
// wants to react to alerts (useAlertListener) all read from here.
const AlertsContext = createContext(null)
const TOAST_MS = 6000
const FEED_MAX = 50

export function AlertsProvider({ children }) {
  const [feed, setFeed] = useState([])
  const [toasts, setToasts] = useState([])
  const [unread, setUnread] = useState(0)
  const [connected, setConnected] = useState(false)
  const listeners = useRef(new Set())

  useEffect(() => {
    getAlerts().then(
      (history) => setFeed((f) => [...f, ...history.filter((h) => !f.some((a) => a.id === h.id))].slice(0, FEED_MAX)),
      () => {},
    )
    const stream = new EventSource(alertStreamUrl())
    stream.onopen = () => setConnected(true)
    stream.onerror = () => setConnected(false) // EventSource reconnects by itself
    stream.addEventListener('alert', (e) => {
      const alert = JSON.parse(e.data)
      setFeed((f) => [alert, ...f.filter((a) => a.id !== alert.id)].slice(0, FEED_MAX))
      setToasts((t) => [...t.filter((a) => a.id !== alert.id), alert].slice(-4))
      setUnread((n) => n + 1)
      setTimeout(() => setToasts((t) => t.filter((a) => a.id !== alert.id)), TOAST_MS)
      listeners.current.forEach((fn) => fn(alert))
    })
    return () => stream.close()
  }, [])

  const subscribe = useCallback((fn) => {
    listeners.current.add(fn)
    return () => listeners.current.delete(fn)
  }, [])
  const dismiss = useCallback((id) => setToasts((t) => t.filter((a) => a.id !== id)), [])
  const markRead = useCallback(() => setUnread(0), [])

  return (
    <AlertsContext.Provider value={{ feed, toasts, unread, connected, subscribe, dismiss, markRead }}>
      {children}
    </AlertsContext.Provider>
  )
}

export const useAlerts = () => useContext(AlertsContext)

// Calls fn(alert) for every live alert while the component is mounted.
export function useAlertListener(fn) {
  const { subscribe } = useAlerts()
  const ref = useRef(fn)
  useEffect(() => {
    ref.current = fn
  })
  useEffect(() => subscribe((alert) => ref.current(alert)), [subscribe])
}
