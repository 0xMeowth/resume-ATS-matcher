import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import KeywordPanel from './KeywordPanel'

function AutoTextarea({ value, onChange, className }) {
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = el.scrollHeight + 'px'
    }
  }, [value])

  return (
    <textarea
      ref={ref}
      className={className || 'bullet-textarea'}
      value={value}
      onChange={onChange}
      rows={2}
    />
  )
}

export default function Step4Edit({ resumeSections, skillMatches, onSectionsChange, onDone }) {
  const [ignoredSkills, setIgnoredSkills] = useState(new Set())
  const [flashedPhrases, setFlashedPhrases] = useState(new Set())
  const [flashedRoles, setFlashedRoles] = useState(new Set())
  const prevMatchedRef = useRef(null)
  const flashTimerRef = useRef(null)

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
    if (newlyMatched.size === 0) return

    // Find which role textareas contain the newly matched phrases
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
    }, 600)
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
              {section.roles.map((role, ri) => (
                <div key={ri} className="edit-role">
                  {role.title != null && (
                    <input
                      className="edit-role-title-input"
                      value={role.title}
                      onChange={e => handleRoleTitleChange(si, ri, e.target.value)}
                    />
                  )}
                  <AutoTextarea
                    className={`bullet-textarea${flashedRoles.has(`${si}-${ri}`) ? ' textarea-flash' : ''}`}
                    value={role.bullets.map(b => b.text).join('\n')}
                    onChange={e => handleRoleTextChange(si, ri, e.target.value)}
                  />
                </div>
              ))}
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
        />
      </div>
    </div>
  )
}
