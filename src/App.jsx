import './App.css'
import { useMemo, useState } from 'react'

function App() {
  const [signalMode, setSignalMode] = useState('all')
  const [links, setLinks] = useState('')
  const [socials, setSocials] = useState({
    telegram: true,
    reddit: false,
  })

  const selectedNetworks = useMemo(
    () => Object.entries(socials).filter(([, isSelected]) => isSelected).map(([name]) => name),
    [socials],
  )

  const handleSocialChange = (networkName) => {
    setSocials((previous) => ({
      ...previous,
      [networkName]: !previous[networkName],
    }))
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    // UI-only screen for now: keep interaction local.
    // eslint-disable-next-line no-console
    console.log({
      signalMode,
      links,
      selectedNetworks,
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
              value={links}
              onChange={(event) => setLinks(event.target.value)}
              placeholder={`https://t.me/example_channel\nhttps://www.reddit.com/r/technology`}
            />
            <p className="field-note">Use one link per line.</p>
          </div>

          <fieldset className="field-group socials">
            <legend className="field-label">Social networks</legend>
            <div className="social-options">
              <label className="checkbox-card">
                <input
                  type="checkbox"
                  checked={socials.telegram}
                  onChange={() => handleSocialChange('telegram')}
                />
                <span>Telegram</span>
              </label>
              <label className="checkbox-card">
                <input
                  type="checkbox"
                  checked={socials.reddit}
                  onChange={() => handleSocialChange('reddit')}
                />
                <span>Reddit</span>
              </label>
            </div>
          </fieldset>

          <footer className="form-footer">
            <p className="status">
              {selectedNetworks.length > 0
                ? `Selected: ${selectedNetworks.join(', ')}`
                : 'Choose at least one social network'}
            </p>
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
