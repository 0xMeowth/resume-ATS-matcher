import React, { useState } from 'react'
// import { submitFeedback } from '../api'  // disabled: feedback collection deprioritised (Stage 8c)

const TYPE_ORDER = { exact: 0, semantic_strong: 1, semantic_weak: 2, missing: 3 }
const TYPE_LABEL = {
  exact: 'Exact',
  semantic_strong: 'Strong',
  semantic_weak: 'Weak',
  missing: 'Missing',
}
const TYPE_CLASS = {
  exact: 'tag-exact',
  semantic_strong: 'tag-strong',
  semantic_weak: 'tag-weak',
  missing: 'tag-missing',
}

export default function Step3Coverage({ skillMatches, debugEvents, stale, analysisId, onNext }) {
  const [showDebug, setShowDebug] = useState(false)
  // const [feedback, setFeedback] = useState({})  // disabled: Stage 8c
  // function handleFeedback(phrase, bulletText, label) { ... }  // disabled: Stage 8c

  const sorted = [...skillMatches].sort((a, b) => {
    const od = (TYPE_ORDER[a.match_type] ?? 9) - (TYPE_ORDER[b.match_type] ?? 9)
    return od !== 0 ? od : a.phrase.localeCompare(b.phrase)
  })

  const counts = skillMatches.reduce((acc, m) => {
    acc[m.match_type] = (acc[m.match_type] || 0) + 1
    return acc
  }, {})

  return (
    <div className="step">
      <h2>3) Coverage report</h2>

      {stale && (
        <p className="warning stale-warning">Job description has changed since this report was generated. Re-run analysis on step 2 to refresh.</p>
      )}

      <div className="summary-row">
        {['exact', 'semantic_strong', 'semantic_weak', 'missing'].map(t => (
          <span key={t} className={`tag ${TYPE_CLASS[t]}`}>
            {TYPE_LABEL[t]}: {counts[t] || 0}
          </span>
        ))}
      </div>

      <table className="coverage-table">
        <thead>
          <tr>
            <th>Skill term</th>
            <th>Match</th>
            <th>Similarity</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(m => (
            <tr key={m.phrase}>
              <td>{m.phrase}</td>
              <td><span className={`tag ${TYPE_CLASS[m.match_type]}`}>{TYPE_LABEL[m.match_type]}</span></td>
              <td>{m.similarity.toFixed(3)}</td>
              <td className="evidence">{m.evidence_text || '—'}</td>
              {/* feedback cell disabled — Stage 8c deprioritised
              <td className="feedback-cell">
                <button className={`feedback-btn${fb === 'covered' ? ' active' : ''}`} ...>+</button>
                <button className={`feedback-btn${fb === 'not_covered' ? ' active' : ''}`} ...>-</button>
              </td>
              */}
            </tr>
          ))}
        </tbody>
      </table>

      {debugEvents && debugEvents.length > 0 && (
        <div className="debug-section">
          <button className="link-btn" onClick={() => setShowDebug(s => !s)}>
            {showDebug ? '▲ Hide debug events' : '▼ Show debug events'} ({debugEvents.length})
          </button>
          {showDebug && (
            <table className="coverage-table">
              <thead>
                <tr><th>Phase</th><th>Source</th><th>Candidate</th><th>Action</th><th>Reason</th></tr>
              </thead>
              <tbody>
                {debugEvents.map((e, i) => (
                  <tr key={i} className={e.action === 'dropped' ? 'row-dropped' : ''}>
                    <td>{e.phase}</td><td>{e.source}</td><td>{e.candidate}</td>
                    <td>{e.action}</td><td>{e.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <button onClick={onNext}>Next: Review suggestions →</button>
    </div>
  )
}
