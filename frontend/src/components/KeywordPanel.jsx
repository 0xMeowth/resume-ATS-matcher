import React, { useRef, useState, useCallback } from 'react'

export default function KeywordPanel({ skillMatches, ignoredSkills, onToggleIgnore, resumeText, flashedPhrases, lostPhrases }) {
  const scrollRef = useRef(null)
  const [showTopFade, setShowTopFade] = useState(false)
  const [showBottomFade, setShowBottomFade] = useState(true)

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    setShowTopFade(el.scrollTop > 4)
    setShowBottomFade(el.scrollTop + el.clientHeight < el.scrollHeight - 4)
  }, [])

  const resumeLower = (resumeText || '').toLowerCase()
  const _escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  const keywords = skillMatches.map(m => {
    const phrase = m.phrase
    const ignored = ignoredSkills.has(phrase)
    const exactMatch = !ignored && new RegExp(`(?<![a-zA-Z0-9])${_escRe(phrase.toLowerCase())}(?![a-zA-Z0-9])`).test(resumeLower)
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

  // Frontend substring deduplication:
  // _suppress_substrings (backend) keeps both "machine learning" and "machine learning
  // models" when the shorter phrase appears independently elsewhere in the JD — by design
  // (the C1 independence clause in jd_parser.py). This is semantically correct but causes
  // double-counting in the panel: typing "machine learning models" turns both green.
  // Fix: suppress any keyword whose phrase is a whole-word substring of another keyword's
  // phrase. The longer phrase is kept; the shorter is hidden. Backend scores are unaffected.
  // NOTE: if a future "repeated phrase ranking" feature is added (more occurrences = higher
  // priority), revisit this dedup — the shorter phrase occurrence count may still be useful.
  const dedupedKeywords = keywords.filter(k =>
    !keywords.some(other =>
      other.phrase !== k.phrase &&
      new RegExp(`\\b${_escRe(k.phrase.toLowerCase())}\\b`).test(other.phrase.toLowerCase())
    )
  )

  const active = dedupedKeywords.filter(k => !k.ignored)
  const matchedCount = active.filter(k => k.exactMatch).length
  const total = active.length
  const pct = total > 0 ? Math.round((matchedCount / total) * 100) : 0

  return (
    <div className="keyword-panel" ref={scrollRef} onScroll={handleScroll}>
      <div className="kp-header">
        <h3 className="kp-title">Keyword Coverage</h3>
        <div className="kp-score">{pct}%</div>
        <div className="kp-progress-track">
          <div className="kp-progress-fill" style={{ width: `${pct}%` }} />
        </div>
        <p className="kp-count">{matchedCount} / {total} exact matches</p>
      </div>

      {showTopFade && <div className="kp-scroll-fade kp-scroll-fade-top" />}
      <ul className="kp-list">
        {dedupedKeywords.map((k, index) => {
          let cls = 'kp-item'
          if (k.ignored) cls += ' kp-ignored'
          else if (k.exactMatch) cls += ' kp-matched'
          else if (k.semanticHint) cls += ' kp-semantic'
          else cls += ' kp-unmatched'
          if (flashedPhrases && flashedPhrases.has(k.phrase)) cls += ' kp-flash'
          if (lostPhrases && lostPhrases.has(k.phrase)) cls += ' kp-flash-pink'

          return (
            <li
              key={k.phrase}
              className={cls}
              style={{ animationDelay: `${index * 30}ms` }}
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
      {showBottomFade && <div className="kp-scroll-fade kp-scroll-fade-bottom" />}
    </div>
  )
}
