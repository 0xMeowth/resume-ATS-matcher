import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import KeywordPanel from './KeywordPanel'

function AutoTextarea({ value, onChange, semantic }) {
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
      className={`bullet-textarea${semantic ? ' bullet-semantic' : ''}`}
      value={value}
      onChange={onChange}
      rows={1}
      title={semantic ? `Semantically covers: ${semantic}` : undefined}
    />
  )
}

export default function Step4Edit({ resumeSections, skillMatches, onSectionsChange, onDone }) {
  const [ignoredSkills, setIgnoredSkills] = useState(new Set())

  const resumeText = useMemo(() => {
    return resumeSections
      .flatMap(s => s.roles.flatMap(r => r.bullets.map(b => b.text)))
      .join(' ')
  }, [resumeSections])

  // Map bullet_id → list of semantically matched keywords (from Step 3, static)
  const semanticBulletMap = useMemo(() => {
    const map = {}
    for (const m of skillMatches) {
      if ((m.match_type === 'semantic_strong' || m.match_type === 'semantic_weak') && m.evidence_bullet_id) {
        if (!map[m.evidence_bullet_id]) map[m.evidence_bullet_id] = []
        map[m.evidence_bullet_id].push(m.phrase)
      }
    }
    return map
  }, [skillMatches])

  const handleBulletChange = useCallback((sectionIdx, roleIdx, bulletIdx, newText) => {
    onSectionsChange(prev => {
      const next = prev.map((s, si) => {
        if (si !== sectionIdx) return s
        return {
          ...s,
          roles: s.roles.map((r, ri) => {
            if (ri !== roleIdx) return r
            return {
              ...r,
              bullets: r.bullets.map((b, bi) => {
                if (bi !== bulletIdx) return b
                return { ...b, text: newText }
              }),
            }
          }),
        }
      })
      return next
    })
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
              <h3 className="edit-section-title">{section.title}</h3>
              {section.roles.map((role, ri) => (
                <div key={ri} className="edit-role">
                  {role.title && <h4 className="edit-role-title">{role.title}</h4>}
                  {role.bullets.map((bullet, bi) => (
                    <AutoTextarea
                      key={bullet.bullet_id}
                      value={bullet.text}
                      onChange={e => handleBulletChange(si, ri, bi, e.target.value)}
                      semantic={semanticBulletMap[bullet.bullet_id]?.join(', ') || null}
                    />
                  ))}
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
        />
      </div>
    </div>
  )
}
