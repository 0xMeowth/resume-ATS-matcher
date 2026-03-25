import React, { useState, useEffect } from 'react'

export default function SuggestionCard({ phrase, originalText, suggestedText, loading, onAccept, onSkip }) {
  const [edited, setEdited] = useState('')

  useEffect(() => {
    if (suggestedText != null) setEdited(suggestedText)
  }, [suggestedText])

  return (
    <div className="suggestion-card">
      <div className="suggestion-card-header">
        <span className="suggestion-badge">{phrase}</span>
        <button className="suggestion-close" onClick={onSkip} title="Dismiss">×</button>
      </div>

      {loading ? (
        <div className="suggestion-skeleton">
          <div className="skeleton-line" />
          <div className="skeleton-line skeleton-short" />
        </div>
      ) : (
        <>
          <div className="suggestion-original">{originalText}</div>
          <div className="suggestion-arrow">↓</div>
          <textarea
            className="suggestion-textarea"
            value={edited}
            onChange={e => setEdited(e.target.value)}
            rows={3}
          />
          <div className="suggestion-actions">
            <button className="btn-accept" onClick={() => onAccept(edited)}>Use this</button>
            <button className="btn-skip" onClick={onSkip}>Skip</button>
          </div>
        </>
      )}
    </div>
  )
}
