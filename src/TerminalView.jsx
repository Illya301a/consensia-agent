import { useEffect, useRef, useState } from 'react'
import './TerminalView.css'

const MAX_LOG_LINES = 100

export function TerminalView({ onClose, wsLogsUrl }) {
  const [lines, setLines] = useState([])
  const [wsState, setWsState] = useState('connecting')
  const scrollRef = useRef(null)

  useEffect(() => {
    let ws
    try {
      ws = new WebSocket(wsLogsUrl)
    } catch {
      setWsState('error')
      return undefined
    }

    setWsState('connecting')
    ws.onopen = () => setWsState('open')
    ws.onmessage = (event) => {
      const text = typeof event.data === 'string' ? event.data : String(event.data)
      setLines((prev) => {
        const next = [...prev, text]
        return next.length > MAX_LOG_LINES ? next.slice(-MAX_LOG_LINES) : next
      })
    }
    ws.onerror = () => setWsState('error')
    ws.onclose = () => {
      setWsState((prev) => (prev === 'connecting' ? 'error' : 'closed'))
    }

    return () => {
      ws.close()
    }
  }, [wsLogsUrl])

  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [lines])

  const statusLabel =
    wsState === 'open'
      ? 'Connected'
      : wsState === 'connecting'
        ? 'Connecting…'
        : wsState === 'closed'
          ? 'Disconnected'
          : 'Connection error'

  return (
    <section className="terminal-view card" aria-label="Agent logs">
      <header className="terminal-view-header">
        <div>
          <h1 className="terminal-view-title">Live logs</h1>
          <p className={`terminal-ws-status terminal-ws-status-${wsState}`}>{statusLabel}</p>
        </div>
        <button type="button" className="terminal-back-btn" onClick={onClose}>
          Back to dashboard
        </button>
      </header>
      <div ref={scrollRef} className="terminal-scroll" tabIndex={0}>
        <pre className="terminal-pre">{lines.length === 0 ? 'Waiting for log lines…\n' : lines.join('\n')}</pre>
      </div>
    </section>
  )
}
