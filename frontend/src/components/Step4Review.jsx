import React from 'react'

export default function Step4Review({ suggestions, edits, onEditChange, acceptedChanges, onAcceptChange, onDone }) {
  function toggleAccept(bulletId, checked) {
    onAcceptChange(a => {
      const next = { ...a }
      if (checked) next[bulletId] = edits[bulletId]
      else delete next[bulletId]
      return next
    })
  }

  function updateEdit(bulletId, text) {
    onEditChange(e => ({ ...e, [bulletId]: text }))
    onAcceptChange(a => {
      if (bulletId in a) return { ...a, [bulletId]: text }
      return a
    })
  }

  if (suggestions.length === 0) {
    return (
      <div className="step">
        <h2>4) Review suggestions</h2>
        <p>No suggestions generated for this JD.</p>
        <button onClick={onDone}>Proceed to export →</button>
      </div>
    )
  }

  return (
    <div className="step">
      <h2>4) Review suggestions</h2>
      <p>{Object.keys(acceptedChanges).length} of {suggestions.length} changes accepted</p>

      {suggestions.map((s, i) => (
        <div key={s.bullet_id} className="suggestion-card">
          <div className="suggestion-header">
            <strong>Bullet {i + 1}</strong>
            <span className="keyword-tag">{s.phrase}</span>
          </div>
          <p className="hint">{s.suggestion_text}</p>
          <textarea
            rows={3}
            value={edits[s.bullet_id] ?? s.original_text}
            onChange={e => updateEdit(s.bullet_id, e.target.value)}
          />
          <label>
            <input
              type="checkbox"
              checked={!!acceptedChanges[s.bullet_id]}
              onChange={e => toggleAccept(s.bullet_id, e.target.checked)}
            />
            {' '}Accept this change
          </label>
        </div>
      ))}

      <button onClick={onDone}>
        Apply {Object.keys(acceptedChanges).length} change{Object.keys(acceptedChanges).length !== 1 ? 's' : ''} & export →
      </button>
    </div>
  )
}
