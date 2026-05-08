import './App.css'
import { useState } from 'react'

function App() {
  const [signalMode, setSignalMode] = useState('all')
  const [linkInput, setLinkInput] = useState('')
  const [savedLinks, setSavedLinks] = useState([])
  const [selectedSocial, setSelectedSocial] = useState('telegram')

  const normalizedInput = linkInput.trim()
  const canSaveLink = normalizedInput.length > 0

  const handleSaveLink = () => {
    if (!canSaveLink) return

    const newLinks = normalizedInput
      .split('\n')
      .map((link) => link.trim())
      .filter(Boolean)

    if (newLinks.length === 0) return

    setSavedLinks((previous) => [...previous, ...newLinks])
    setLinkInput('')
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    // UI-only screen for now: keep interaction local.
    // eslint-disable-next-line no-console
    console.log({
      signalMode,
      selectedSocial,
      savedLinks,
    })
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
                  {savedLinks.map((link, index) => (
                    <li key={`${link}-${index}`} className="saved-link-item">
                      {link}
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
