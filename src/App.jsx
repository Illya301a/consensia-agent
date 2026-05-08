import './App.css'
import { useEffect, useRef, useState } from 'react'
import { validateLinkForSocial } from './utils/linkValidation'

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

const SIGNAL_MODE_OPTIONS = [
  { value: 'all', label: 'Send all signals' },
  { value: 'high', label: 'Send only high signals' },
]

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
  const [linkError, setLinkError] = useState('')
  const [isSignalMenuOpen, setIsSignalMenuOpen] = useState(false)
  const signalMenuRef = useRef(null)

  const normalizedInput = linkInput.trim()

  const handleSaveLink = () => {
    if (!normalizedInput) {
      setLinkError('Please paste at least one link before saving.')
      return
    }

    const newLinks = normalizedInput
      .split('\n')
      .map((link) => link.trim())
      .filter(Boolean)

    if (newLinks.length === 0) return

    const parsedLinks = []
    for (const rawLink of newLinks) {
      const validationResult = validateLinkForSocial(rawLink, selectedSocial)
      if (!validationResult.ok) {
        setLinkError(validationResult.error)
        return
      }

      parsedLinks.push(validationResult.value)
    }

    setLinkError('')
    setSavedLinks((previous) => [...previous, ...parsedLinks.map((url) => createLinkItem(url))])
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

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (!signalMenuRef.current?.contains(event.target)) {
        setIsSignalMenuOpen(false)
      }
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsSignalMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [])

  useEffect(() => {
    if (!linkError) return undefined

    const timerId = window.setTimeout(() => {
      setLinkError('')
    }, 3500)

    return () => {
      window.clearTimeout(timerId)
    }
  }, [linkError])

  const handleSubmit = (event) => {
    event.preventDefault()
    const payload = {
      signalMode,
      selectedSocial,
      savedLinks,
      updatedAt: Date.now(),
    }
    persistSettings(payload)
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
            <div
              id="signal-mode"
              className={`signal-mode-select${isSignalMenuOpen ? ' signal-mode-select-open' : ''}`}
              ref={signalMenuRef}
            >
              <button
                type="button"
                className="signal-mode-trigger"
                onClick={() => setIsSignalMenuOpen((previous) => !previous)}
                aria-expanded={isSignalMenuOpen}
                aria-haspopup="listbox"
              >
                <span>{SIGNAL_MODE_OPTIONS.find((option) => option.value === signalMode)?.label}</span>
                <span className="signal-mode-chevron" aria-hidden="true">
                  ▾
                </span>
              </button>
              {isSignalMenuOpen && (
                <ul className="signal-mode-menu" role="listbox" aria-label="Signal mode options">
                  {SIGNAL_MODE_OPTIONS.map((option) => (
                    <li key={option.value}>
                      <button
                        type="button"
                        className={`signal-mode-option${signalMode === option.value ? ' signal-mode-option-active' : ''}`}
                        onClick={() => {
                          setSignalMode(option.value)
                          setIsSignalMenuOpen(false)
                        }}
                        role="option"
                        aria-selected={signalMode === option.value}
                      >
                        {option.label}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="field-group">
            <label htmlFor="links" className="field-label">
              Links to parse
            </label>
            <div className="link-input-row">
              <textarea
                id="links"
                className="field-control field-control-area"
                value={linkInput}
                onChange={(event) => {
                  setLinkInput(event.target.value)
                  if (linkError) setLinkError('')
                }}
                placeholder={`https://t.me/example_channel\nhttps://www.reddit.com/r/technology`}
              />
              <div className="link-actions">
                <button type="button" className="save-link-btn" onClick={handleSaveLink}>
                  Save link
                </button>
              </div>
            </div>
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
                  onChange={() => {
                    setSelectedSocial('telegram')
                    if (linkError) setLinkError('')
                  }}
                />
                <span>Telegram</span>
              </label>
              <label className="checkbox-card">
                <input
                  type="radio"
                  name="social-network"
                  checked={selectedSocial === 'reddit'}
                  onChange={() => {
                    setSelectedSocial('reddit')
                    if (linkError) setLinkError('')
                  }}
                />
                <span>Reddit</span>
              </label>
            </div>
          </fieldset>

          <footer className="form-footer">
            <button type="submit" className="submit-btn">
              Save settings
            </button>
          </footer>
        </form>
      </section>
      <div className="page-error-layer" aria-live="polite" aria-atomic="true">
        <p
          className={`field-error${linkError ? ' field-error-visible' : ''}`}
          onClick={() => setLinkError('')}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              setLinkError('')
            }
          }}
        >
          {linkError}
        </p>
      </div>
    </main>
  )
}

export default App
