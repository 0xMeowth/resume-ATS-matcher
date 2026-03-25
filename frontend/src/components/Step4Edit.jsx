import React, { useState, useMemo, useCallback, useRef, useEffect, useLayoutEffect } from 'react'
import KeywordPanel from './KeywordPanel'

function AutoTextarea({ value, onChange, className }) {
  const ref = useRef(null)
  const undoStackRef = useRef([value])
  const redoStackRef = useRef([])
  const lastSnapshotRef = useRef(value)
  const snapshotTimerRef = useRef(null)

  const displayValue = value
    .split('\n')
    .map(l => '• ' + l)
    .join('\n')

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.minHeight = '0'
    el.style.height = '0'
    const sh = el.scrollHeight
    const fontSize = parseFloat(getComputedStyle(el).fontSize)
    const minH = Math.round(4 * 1.6 * fontSize + 24)
    const finalH = Math.max(sh, minH)
    const maxH = 400
    el.style.height = finalH + 'px'
    el.style.overflowY = finalH > maxH ? 'auto' : 'hidden'
  }, [displayValue])

  const takeSnapshot = useCallback((val) => {
    if (val !== lastSnapshotRef.current) {
      undoStackRef.current.push(val)
      redoStackRef.current = []
      lastSnapshotRef.current = val
      if (undoStackRef.current.length > 50) undoStackRef.current.shift()
    }
  }, [])

  const handleChange = (e) => {
    const el = e.target
    const pos = el.selectionStart
    const raw = el.value
    const lines = raw.split('\n')
    const clean = lines.map(l => l.replace(/^• ?/, '')).join('\n')
    onChange({ target: { value: clean } })

    // Debounce undo snapshots (group rapid keystrokes)
    clearTimeout(snapshotTimerRef.current)
    snapshotTimerRef.current = setTimeout(() => takeSnapshot(clean), 400)

    // Cursor adjustment: account for bullet prefixes re-added by display transform
    let charsSoFar = 0
    let linesUpToCursor = 0
    for (const line of lines) {
      if (charsSoFar + line.length >= pos) break
      charsSoFar += line.length + 1
      linesUpToCursor++
    }
    const n = linesUpToCursor + 1
    const rawBullets = lines.slice(0, n).reduce((s, l) => {
      const m = l.match(/^• ?/)
      return s + (m ? m[0].length : 0)
    }, 0)
    const displayBullets = n * 2

    requestAnimationFrame(() => {
      if (!ref.current) return
      const expected = clean.split('\n').map(l => '• ' + l).join('\n')
      if (ref.current.value !== expected) {
        ref.current.value = expected
        ref.current.style.height = '0'
        ref.current.style.height = ref.current.scrollHeight + 'px'
      }
      const adj = displayBullets - rawBullets
      if (adj !== 0) {
        const p = pos + adj
        ref.current.selectionStart = p
        ref.current.selectionEnd = p
      }
    })
  }

  const handleKeyDown = useCallback((e) => {
    const mod = e.metaKey || e.ctrlKey
    if (!mod) return

    if (e.key === 'z' && !e.shiftKey) {
      e.preventDefault()
      // Snapshot current state before undoing
      takeSnapshot(value)
      if (undoStackRef.current.length > 1) {
        const current = undoStackRef.current.pop()
        redoStackRef.current.push(current)
        const prev = undoStackRef.current[undoStackRef.current.length - 1]
        lastSnapshotRef.current = prev
        onChange({ target: { value: prev } })
      }
    } else if (e.key === 'y' || (e.key === 'z' && e.shiftKey)) {
      e.preventDefault()
      if (redoStackRef.current.length > 0) {
        const next = redoStackRef.current.pop()
        undoStackRef.current.push(next)
        lastSnapshotRef.current = next
        onChange({ target: { value: next } })
      }
    }
  }, [value, onChange, takeSnapshot])

  return (
    <textarea
      ref={ref}
      className={className || 'bullet-textarea'}
      value={displayValue}
      onChange={handleChange}
      onKeyDown={handleKeyDown}
      rows={1}
    />
  )
}

export default function Step4Edit({ resumeSections, skillMatches, onSectionsChange, onDone }) {
  const [ignoredSkills, setIgnoredSkills] = useState(new Set())
  const [flashedPhrases, setFlashedPhrases] = useState(new Set())
  const [flashedRoles, setFlashedRoles] = useState(new Set())
  const [lostPhrases, setLostPhrases] = useState(new Set())
  const [lostRoles, setLostRoles] = useState(new Set())
  const prevMatchedRef = useRef(null)
  const flashTimerRef = useRef(null)
  const lostTimerRef = useRef(null)

  const _escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  const resumeText = useMemo(() => {
    return resumeSections
      .flatMap(s => s.roles.flatMap(r => r.bullets.map(b => b.text)))
      .join(' ')
  }, [resumeSections])

  // Detect newly matched keywords and trigger flash
  useEffect(() => {
    if (!skillMatches.length) return
    const resumeLower = resumeText.toLowerCase()
    const currentMatched = new Set(
      skillMatches
        .filter(m => !ignoredSkills.has(m.phrase))
        .filter(m => new RegExp(`(?<![a-zA-Z0-9])${_escRe(m.phrase.toLowerCase())}(?![a-zA-Z0-9])`).test(resumeLower))
        .map(m => m.phrase)
    )

    const prev = prevMatchedRef.current
    prevMatchedRef.current = currentMatched
    if (!prev) return // first render — no flash

    const newlyMatched = new Set()
    for (const p of currentMatched) {
      if (!prev.has(p)) newlyMatched.add(p)
    }
    const newlyLost = new Set()
    for (const p of prev) {
      if (!currentMatched.has(p)) newlyLost.add(p)
    }

    if (newlyMatched.size === 0 && newlyLost.size === 0) return

    // Green flash: newly matched keywords
    if (newlyMatched.size > 0) {
      const rolesWithFlash = new Set()
      resumeSections.forEach((section, si) => {
        section.roles.forEach((role, ri) => {
          const roleText = role.bullets.map(b => b.text).join('\n').toLowerCase()
          for (const phrase of newlyMatched) {
            if (new RegExp(`(?<![a-zA-Z0-9])${_escRe(phrase.toLowerCase())}(?![a-zA-Z0-9])`).test(roleText)) {
              rolesWithFlash.add(`${si}-${ri}`)
            }
          }
        })
      })
      setFlashedPhrases(newlyMatched)
      setFlashedRoles(rolesWithFlash)
      clearTimeout(flashTimerRef.current)
      flashTimerRef.current = setTimeout(() => {
        setFlashedPhrases(new Set())
        setFlashedRoles(new Set())
      }, 900)
    }

    // Pink flash: newly lost keywords (last occurrence removed)
    if (newlyLost.size > 0) {
      // Flash the currently focused textarea (the one being edited)
      const lostRoleKeys = new Set()
      const active = document.activeElement
      if (active && active.tagName === 'TEXTAREA') {
        const roleEl = active.closest('.edit-role')
        if (roleEl) {
          const sectionEl = roleEl.closest('.edit-section')
          if (sectionEl) {
            const sections = [...sectionEl.parentElement.querySelectorAll('.edit-section')]
            const roles = [...sectionEl.querySelectorAll('.edit-role')]
            const si = sections.indexOf(sectionEl)
            const ri = roles.indexOf(roleEl)
            if (si >= 0 && ri >= 0) lostRoleKeys.add(`${si}-${ri}`)
          }
        }
      }
      setLostPhrases(newlyLost)
      setLostRoles(lostRoleKeys)
      clearTimeout(lostTimerRef.current)
      lostTimerRef.current = setTimeout(() => {
        setLostPhrases(new Set())
        setLostRoles(new Set())
      }, 900)
    }
  }, [resumeText, skillMatches, ignoredSkills])

  const handleSectionTitleChange = useCallback((sectionIdx, newTitle) => {
    onSectionsChange(prev =>
      prev.map((s, si) => si !== sectionIdx ? s : { ...s, title: newTitle })
    )
  }, [onSectionsChange])

  const handleRoleTitleChange = useCallback((sectionIdx, roleIdx, newTitle) => {
    onSectionsChange(prev =>
      prev.map((s, si) => {
        if (si !== sectionIdx) return s
        return {
          ...s,
          roles: s.roles.map((r, ri) =>
            ri !== roleIdx ? r : { ...r, title: newTitle }
          ),
        }
      })
    )
  }, [onSectionsChange])

  const handleRoleTextChange = useCallback((sectionIdx, roleIdx, fullText) => {
    const lines = fullText.split('\n')
    onSectionsChange(prev =>
      prev.map((s, si) => {
        if (si !== sectionIdx) return s
        return {
          ...s,
          roles: s.roles.map((r, ri) => {
            if (ri !== roleIdx) return r
            const newBullets = lines.map((line, li) => {
              if (li < r.bullets.length) {
                return { ...r.bullets[li], text: line }
              }
              return {
                bullet_id: `new-${crypto.randomUUID()}`,
                text: line,
                paragraph_index: -1,
              }
            })
            return { ...r, bullets: newBullets }
          }),
        }
      })
    )
  }, [onSectionsChange])

  const toggleIgnore = useCallback((phrase) => {
    setIgnoredSkills(prev => {
      const next = new Set(prev)
      if (next.has(phrase)) next.delete(phrase)
      else next.add(phrase)
      return next
    })
  }, [])

  return (
    <div className="edit-layout">
      <div className="edit-cv">
        <div className="step">
          <h2>4) Edit Resume</h2>

          {resumeSections.length === 0 && (
            <p className="muted">No resume sections found. Please upload a resume first.</p>
          )}

          {resumeSections.map((section, si) => (
            <div key={si} className="edit-section">
              <input
                className="edit-section-title-input"
                value={section.title}
                onChange={e => handleSectionTitleChange(si, e.target.value)}
              />
              {section.roles.map((role, ri) => {
                const roleValue = role.bullets
                  .map(b => b.text)
                  .filter((t, i, arr) => t.trim() || arr.slice(i).some(x => x.trim()))
                  .join('\n')
                return (
                  <div key={ri} className="edit-role">
                    {role.title != null && (
                      <input
                        className="edit-role-title-input"
                        value={role.title}
                        onChange={e => handleRoleTitleChange(si, ri, e.target.value)}
                      />
                    )}
                    {role.bullets.length > 0 && (
                      <AutoTextarea
                        className={`bullet-textarea${flashedRoles.has(`${si}-${ri}`) ? ' textarea-flash' : lostRoles.has(`${si}-${ri}`) ? ' textarea-flash-pink' : ''}`}
                        value={roleValue}
                        onChange={e => handleRoleTextChange(si, ri, e.target.value)}
                      />
                    )}
                  </div>
                )
              })}
            </div>
          ))}

          <button onClick={onDone} style={{ marginTop: 16 }}>
            Export &rarr;
          </button>
        </div>
      </div>

      <div className="keyword-panel-wrapper">
        <KeywordPanel
          skillMatches={skillMatches}
          ignoredSkills={ignoredSkills}
          onToggleIgnore={toggleIgnore}
          resumeText={resumeText}
          flashedPhrases={flashedPhrases}
          lostPhrases={lostPhrases}
        />
      </div>
    </div>
  )
}
