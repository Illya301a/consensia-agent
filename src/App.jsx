import './App.css'
import { useCallback, useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'
const CHANNEL_IDS_STORAGE_KEY = 'consensia.selectedChannelIds'

const readStoredChannelIds = () => {
  try {
    const raw = localStorage.getItem(CHANNEL_IDS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'string') : []
  } catch {
    return []
  }
}

const persistChannelIds = (ids) => {
  localStorage.setItem(CHANNEL_IDS_STORAGE_KEY, JSON.stringify(ids))
}

function App() {
  const [telegramSources, setTelegramSources] = useState([])
  const [selectedChannelIds, setSelectedChannelIds] = useState(readStoredChannelIds)
  const [agentRunning, setAgentRunning] = useState(false)
  const [togglePending, setTogglePending] = useState(false)
  const [savePending, setSavePending] = useState(false)
  const [banner, setBanner] = useState({ type: '', text: '' })

  useEffect(() => {
    persistChannelIds(selectedChannelIds)
  }, [selectedChannelIds])

  useEffect(() => {
    fetch(`${API_BASE}/api/status`)
      .then((res) => res.json())
      .then((data) => setAgentRunning(Boolean(data?.running)))
      .catch(() => {
        setBanner({ type: 'error', text: 'Could not load agent status. Is the backend running?' })
      })

    fetch(`${API_BASE}/api/sources`)
      .then((res) => res.json())
      .then((data) => {
        const list = Array.isArray(data?.telegram) ? data.telegram : []
        setTelegramSources(list)
      })
      .catch(() => {
        setBanner({ type: 'error', text: 'Could not load Telegram sources.' })
      })
  }, [])

  useEffect(() => {
    if (!banner.text) return undefined
    const t = window.setTimeout(() => setBanner({ type: '', text: '' }), 5000)
    return () => window.clearTimeout(t)
  }, [banner.text])

  const toggleChannel = useCallback((channelId) => {
    const id = String(channelId)
    setSelectedChannelIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }, [])

  const handleSaveConfiguration = () => {
    setSavePending(true)
    setBanner({ type: '', text: '' })
    fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ channels: selectedChannelIds }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text().catch(() => res.statusText))
        return res.json()
      })
      .then(() => {
        setBanner({ type: 'success', text: 'Configuration saved on the server.' })
      })
      .catch((err) => {
        setBanner({ type: 'error', text: err.message || 'Failed to save configuration.' })
      })
      .finally(() => setSavePending(false))
  }

  const handleToggleAgent = () => {
    setTogglePending(true)
    setBanner({ type: '', text: '' })
    fetch(`${API_BASE}/api/toggle`, { method: 'POST' })
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text().catch(() => res.statusText))
        return res.json()
      })
      .then((data) => {
        setAgentRunning(Boolean(data?.running))
        setBanner({
          type: 'success',
          text: data?.running ? 'Agent started.' : 'Agent stopped.',
        })
      })
      .catch((err) => {
        setBanner({ type: 'error', text: err.message || 'Could not toggle agent.' })
      })
      .finally(() => setTogglePending(false))
  }

  return (
    <main className="page">
      <section className="card" aria-labelledby="page-title">
        <header className="hero">
          <p className="badge">Consensia Agent</p>
          <h1 id="page-title">Telegram monitor</h1>
          <p className="subtitle">
            Pick channels your userbot can see, save them to the server, then start the agent.
          </p>
          <p className="agent-status-line" aria-live="polite">
            Agent:{' '}
            <span className={agentRunning ? 'agent-status-on' : 'agent-status-off'}>
              {agentRunning ? 'running' : 'stopped'}
            </span>
          </p>
        </header>

        <div className="control-bar">
          <button
            type="button"
            className={`agent-toggle-btn${agentRunning ? ' agent-toggle-btn-on' : ''}`}
            onClick={handleToggleAgent}
            disabled={togglePending}
          >
            {togglePending ? '…' : agentRunning ? 'Stop agent' : 'Start agent'}
          </button>
          <button
            type="button"
            className="submit-btn save-config-btn"
            onClick={handleSaveConfiguration}
            disabled={savePending}
          >
            {savePending ? 'Saving…' : 'Save configuration'}
          </button>
        </div>

        {banner.text ? (
          <p className={`app-banner app-banner-${banner.type}`} role="status">
            {banner.text}
          </p>
        ) : null}

        <section className="channels-panel" aria-labelledby="channels-heading">
          <div className="channels-panel-head">
            <h2 id="channels-heading" className="sources-heading">
              Telegram channels
            </h2>
            <p className="channels-hint">
              {selectedChannelIds.length} selected — click a row to toggle.
            </p>
          </div>
          {telegramSources.length === 0 ? (
            <p className="sources-empty">No channels loaded yet. Start the backend and ensure the userbot has dialogs.</p>
          ) : (
            <ul className="channel-list" role="list">
              {telegramSources.map((ch) => {
                const id = String(ch.id)
                const selected = selectedChannelIds.includes(id)
                const username = typeof ch.username === 'string' ? ch.username.trim() : ''
                return (
                  <li key={id}>
                    <button
                      type="button"
                      className={`channel-tile${selected ? ' channel-tile-selected' : ''}`}
                      onClick={() => toggleChannel(id)}
                      aria-pressed={selected}
                    >
                      <span className={`channel-tile-check${selected ? ' channel-tile-check-on' : ''}`} aria-hidden="true" />
                      <span className="channel-tile-body">
                        <span className="channel-tile-name">{ch.name || username || id}</span>
                        {username ? (
                          <span className="channel-tile-username">@{username}</span>
                        ) : (
                          <span className="channel-tile-username channel-tile-username-missing">No public username</span>
                        )}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </section>
    </main>
  )
}

export default App
