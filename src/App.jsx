import './App.css'
import { useEffect, useState } from 'react'

const STORAGE_KEY = 'consensia.settings'

const readStoredSettings = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed
  } catch {
    return null
  }
}

const createLinkItem = (url) => ({
  id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  url,
})

function App() {
  const initialSettings = readStoredSettings()
  const [signalMode, setSignalMode] = useState(initialSettings?.signalMode ?? 'all')
  const [linkInput, setLinkInput] = useState('')
  const [savedLinks, setSavedLinks] = useState(
    Array.isArray(initialSettings?.savedLinks)
      ? initialSettings.savedLinks.filter((link) => link && typeof link.id === 'string' && typeof link.url === 'string')
      : [],
  )
  const [selectedSocial, setSelectedSocial] = useState(initialSettings?.selectedSocial ?? 'telegram')

  const normalizedInput = linkInput.trim()
  const canSaveLink = normalizedInput.length > 0

  const handleSaveLink = () => {
    if (!canSaveLink) return

    const newLinks = normalizedInput
      .split('\n')
      .map((link) => link.trim())
      .filter(Boolean)

    if (newLinks.length === 0) return

    setSavedLinks((previous) => [...previous, ...newLinks.map((url) => createLinkItem(url))])
    setLinkInput('')
  }

  const handleDeleteLink = (linkId) => {
    setSavedLinks((previous) => previous.filter((link) => link.id !== linkId))
  }

  const persistSettings = (settings) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  }

  useEffect(() => {
    persistSettings({
      signalMode,
      selectedSocial,
      savedLinks,
      updatedAt: Date.now(),
    })
  }, [signalMode, selectedSocial, savedLinks])

  const handleSubmit = (event) => {
    event.preventDefault()
    const payload = {
      signalMode,
      selectedSocial,
      savedLinks,
      updatedAt: Date.now(),
    }
    persistSettings(payload)
    // eslint-disable-next-line no-console
    console.log(payload)
  }

  return (
    <main className="page">
      <section className="card" aria-labelledby="page-title">
        <header className="hero">
          <p className="badge">Consensia Agent</p>
          <h1 id="page-title">Signal Parser Settings</h1>
          <p className="subtitle">
            Choose how to send signals and add links for parsing in Telegram and Reddit.
          </p>
        </header>

        <form className="form" onSubmit={handleSubmit}>
          <div className="field-group">
            <label htmlFor="signal-mode" className="field-label">
              Signal mode
            </label>
            <select
              id="signal-mode"
              className="field-control"
              value={signalMode}
              onChange={(event) => setSignalMode(event.target.value)}
            >
              <option value="all">Send all signals</option>
              <option value="high">Send only high signals</option>
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="links" className="field-label">
              Links to parse
            </label>
            <textarea
              id="links"
              className="field-control field-control-area"
              value={linkInput}
              onChange={(event) => setLinkInput(event.target.value)}
              placeholder={`https://t.me/example_channel\nhttps://www.reddit.com/r/technology`}
            />
            {canSaveLink && (
              <div className="link-actions">
                <button type="button" className="save-link-btn" onClick={handleSaveLink}>
                  Save link
                </button>
              </div>
            )}
            <p className="field-note">Paste one or multiple links (one per line), then click Save link.</p>
            {savedLinks.length > 0 && (
              <div className="saved-links">
                <h2 className="saved-links-title">Saved links</h2>
                <ul className="saved-links-list">
                  {savedLinks.map((link) => (
                    <li key={link.id} className="saved-link-item">
                      <span className="saved-link-text">{link.url}</span>
                      <button
                        type="button"
                        className="remove-link-btn"
                        onClick={() => handleDeleteLink(link.id)}
                        aria-label={`Remove link ${link.url}`}
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <fieldset className="field-group socials">
            <legend className="field-label">Social network</legend>
            <div className="social-options">
              <label className="checkbox-card">
                <input
                  type="radio"
                  name="social-network"
                  checked={selectedSocial === 'telegram'}
                  onChange={() => setSelectedSocial('telegram')}
                />
                <span>Telegram</span>
              </label>
              <label className="checkbox-card">
                <input
                  type="radio"
                  name="social-network"
                  checked={selectedSocial === 'reddit'}
                  onChange={() => setSelectedSocial('reddit')}
                />
                <span>Reddit</span>
              </label>
            </div>
          </fieldset>

          <footer className="form-footer">
            <p className="status">Selected: {selectedSocial}</p>
            <button type="submit" className="submit-btn">
              Save settings
            </button>
          </footer>
        </form>
      </section>
    </main>
  )
}

export default App
