import React from 'react'

export default function KeywordPanel({ skillMatches, ignoredSkills, onToggleIgnore, resumeText }) {
  const resumeLower = (resumeText || '').toLowerCase()

  const keywords = skillMatches.map(m => {
    const phrase = m.phrase
    const ignored = ignoredSkills.has(phrase)
    const exactMatch = !ignored && resumeLower.includes(phrase.toLowerCase())
    // Static semantic hint from Step 3 analysis (not recomputed on edit)
    const semanticHint = !ignored && !exactMatch &&
      (m.match_type === 'semantic_strong' || m.match_type === 'exact')
    return { phrase, exactMatch, semanticHint, ignored }
  })

  // Sort: unmatched first, semantic (amber), matched (green), ignored last
  keywords.sort((a, b) => {
    const order = k => k.ignored ? 3 : k.exactMatch ? 2 : k.semanticHint ? 1 : 0
    return order(a) - order(b)
  })

  const active = keywords.filter(k => !k.ignored)
  const matchedCount = active.filter(k => k.exactMatch).length
  const total = active.length
  const pct = total > 0 ? Math.round((matchedCount / total) * 100) : 0

  return (
    <div className="keyword-panel">
      <h3 className="kp-title">Keyword Coverage</h3>
      <div className="kp-score">{pct}%</div>
      <div className="kp-progress-track">
        <div className="kp-progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="kp-count">{matchedCount} / {total} exact matches</p>

      <ul className="kp-list">
        {keywords.map(k => {
          let cls = 'kp-item'
          if (k.ignored) cls += ' kp-ignored'
          else if (k.exactMatch) cls += ' kp-matched'
          else if (k.semanticHint) cls += ' kp-semantic'
          else cls += ' kp-unmatched'

          return (
            <li
              key={k.phrase}
              className={cls}
              title={k.semanticHint ? 'Semantically covered — add exact phrase for ATS' : undefined}
            >
              <span className="kp-icon">
                {k.ignored ? '—' : k.exactMatch ? '✓' : k.semanticHint ? '~' : '✗'}
              </span>
              <span className="kp-phrase">{k.phrase}</span>
              <button
                className="kp-ignore-btn"
                title={k.ignored ? 'Restore keyword' : 'Ignore keyword'}
                onClick={() => onToggleIgnore(k.phrase)}
              >
                {k.ignored ? '↩' : '×'}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
