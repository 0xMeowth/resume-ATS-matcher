import React, { useState, useEffect, useRef, useLayoutEffect, useCallback } from 'react'

function tokenise(text) {
  return text.split(/(\s+)/)
}

function wordDiff(original, suggested) {
  const a = tokenise(original)
  const b = tokenise(suggested)
  const m = a.length, n = b.length
  const dp = Array.from({ length: m + 1 }, () => new Uint16Array(n + 1))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }
  const parts = []
  let i = m, j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      parts.unshift({ type: 'same', text: a[i - 1] })
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      parts.unshift({ type: 'add', text: b[j - 1] })
      j--
    } else {
      parts.unshift({ type: 'del', text: a[i - 1] })
      i--
    }
  }
  return parts
}

export default function SuggestionCard({
  phrase, originalText, suggestedText, loading,
  onAccept, onSkip, collapsed, onToggleCollapse,
}) {
  const [edited, setEdited] = useState('')
  const taRef = useRef(null)

  useEffect(() => {
    if (suggestedText != null) setEdited(suggestedText)
  }, [suggestedText])

  const resizeTextarea = useCallback(() => {
    const el = taRef.current
    if (!el) return
    el.style.height = '0'
    el.style.height = el.scrollHeight + 'px'
  }, [])

  useLayoutEffect(() => { resizeTextarea() }, [edited, resizeTextarea])

  useEffect(() => {
    const id = requestAnimationFrame(resizeTextarea)
    return () => cancelAnimationFrame(id)
  }, [resizeTextarea])

  const diff = (!loading && originalText && edited) ? wordDiff(originalText, edited) : null

  // Collapsed chip — click anywhere to expand
  if (collapsed) {
    return (
      <div className="suggestion-chip" onClick={onToggleCollapse} title="Click to expand">
        <span className="suggestion-badge">{phrase}</span>
        <span className="suggestion-chip-preview">
          {suggestedText ? suggestedText.slice(0, 80) + (suggestedText.length > 80 ? '…' : '') : '…'}
        </span>
        <span className="suggestion-chip-actions">
          <span className="suggestion-chip-expand">▼</span>
          <button
            className="suggestion-close"
            onClick={e => { e.stopPropagation(); onSkip() }}
            title="Dismiss"
          >×</button>
        </span>
      </div>
    )
  }

  return (
    <div className="suggestion-card">
      <div className="suggestion-card-header">
        <span className="suggestion-badge">{phrase}</span>
        <span style={{ display: 'flex', gap: 4 }}>
          <button className="suggestion-close" onClick={onToggleCollapse} title="Collapse">▲</button>
          <button className="suggestion-close" onClick={onSkip} title="Dismiss">×</button>
        </span>
      </div>

      {loading ? (
        <div className="suggestion-skeleton">
          <div className="skeleton-line" />
          <div className="skeleton-line skeleton-short" />
        </div>
      ) : (
        <>
          {diff && (
            <div className="suggestion-diff">
              {diff.map((part, i) => {
                if (part.type === 'same') return <span key={i}>{part.text}</span>
                if (part.type === 'del') return <span key={i} className="diff-del">{part.text}</span>
                return <span key={i} className="diff-add">{part.text}</span>
              })}
            </div>
          )}
          <textarea
            ref={taRef}
            className="suggestion-textarea"
            value={edited}
            onChange={e => { setEdited(e.target.value) }}
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
