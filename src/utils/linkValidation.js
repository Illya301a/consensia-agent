const normalizeUrl = (value) => {
  const trimmed = value.trim()
  if (!trimmed) return ''
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
}

const detectSocialByHost = (host) => {
  const normalizedHost = host.toLowerCase().replace(/^www\./, '')
  if (normalizedHost === 't.me' || normalizedHost === 'telegram.me') return 'telegram'
  if (normalizedHost === 'reddit.com' || normalizedHost.endsWith('.reddit.com') || normalizedHost === 'redd.it') {
    return 'reddit'
  }
  return null
}

const hasNestedUrlFragments = (value) => /https?:\/\/|www\./i.test(value)

const isTelegramPathValid = (url) => {
  const segments = url.pathname.split('/').filter(Boolean)
  if (segments.length === 0) return false

  const [first, second] = segments
  if (first === 'joinchat' || first === 'c') {
    return typeof second === 'string' && /^[A-Za-z0-9_-]{5,}$/.test(second)
  }

  if (first.startsWith('+')) {
    return /^[A-Za-z0-9_-]{5,}$/.test(first.slice(1))
  }

  return /^[A-Za-z0-9_]{4,32}$/.test(first)
}

const isRedditPathValid = (url) => {
  const host = url.hostname.toLowerCase().replace(/^www\./, '')
  const segments = url.pathname.split('/').filter(Boolean)
  if (segments.length === 0) return false

  if (host === 'redd.it') {
    return /^[A-Za-z0-9]+$/.test(segments[0])
  }

  if (segments[0] === 'r' || segments[0] === 'u' || segments[0] === 'user') {
    return typeof segments[1] === 'string' && /^[A-Za-z0-9_]+$/.test(segments[1])
  }

  return false
}

export const validateLinkForSocial = (rawLink, selectedSocial) => {
  try {
    const preparedUrl = normalizeUrl(rawLink)
    const protocolHits = preparedUrl.match(/https?:\/\//gi)?.length ?? 0
    if (protocolHits > 1) {
      return { ok: false, error: 'Link looks malformed (contains multiple URL parts).' }
    }

    const parsed = new URL(preparedUrl)
    const detectedSocial = detectSocialByHost(parsed.hostname)
    if (!detectedSocial) {
      return { ok: false, error: 'Only Telegram (t.me) and Reddit (reddit.com, redd.it) links are supported.' }
    }

    const tail = `${parsed.pathname}${parsed.search}${parsed.hash}`
    if (hasNestedUrlFragments(tail)) {
      return { ok: false, error: 'Link looks malformed (nested domain/path detected).' }
    }

    if (detectedSocial !== selectedSocial) {
      return {
        ok: false,
        error:
          selectedSocial === 'telegram'
            ? 'Telegram mode: only t.me or telegram.me links are allowed.'
            : 'Reddit mode: only reddit.com or redd.it links are allowed.',
      }
    }

    const isPathValid = detectedSocial === 'telegram' ? isTelegramPathValid(parsed) : isRedditPathValid(parsed)
    if (!isPathValid) {
      return {
        ok: false,
        error:
          detectedSocial === 'telegram'
            ? 'Invalid Telegram link format. Use links like t.me/channel_name.'
            : 'Invalid Reddit link format. Use links like reddit.com/r/subreddit or redd.it/postId.',
      }
    }

    return { ok: true, value: preparedUrl }
  } catch {
    return { ok: false, error: 'Please enter valid links. Example: https://t.me/channel_name' }
  }
}
