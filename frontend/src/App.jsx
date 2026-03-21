import React, { useState, useRef } from 'react'
import Step1Upload from './components/Step1Upload'
import Step2JD from './components/Step2JD'
import Step3Coverage from './components/Step3Coverage'
import Step4Edit from './components/Step4Edit'
import Step5Export from './components/Step5Export'

const STEPS = ['Upload', 'Job Description', 'Coverage', 'Edit Resume', 'Export']

const JD_DEFAULTS = {
  max_skill_terms: 120,
  skill_ranker: 'mmr',
  mmr_diversity: 0.3,
  skill_matching: 'embedding',
  rerank_top_k: 15,
  skill_strong_threshold: 0.7,
  skill_weak_threshold: 0.55,
  debug: false,
}

function StepIndicator({ current, maxStep, staleFrom, onStepClick }) {
  return (
    <div className="step-indicator">
      {STEPS.map((label, i) => {
        const n = i + 1
        const isStale = staleFrom && n >= staleFrom && n <= maxStep
        const isActive = n === current && !isStale
        const isDone = n < current && !isStale
        const isClickable = n <= maxStep && n !== current

        let className = 'step-dot'
        if (isStale) className += ' stale'
        else if (isActive) className += ' active'
        else if (isDone) className += ' done'
        if (isClickable) className += ' clickable'

        return (
          <div
            key={i}
            className={className}
            onClick={() => isClickable && onStepClick(n)}
          >
            <span className="dot">{isDone ? '✓' : n}</span>
            <span className="dot-label">{label}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function App() {
  const [step, setStep] = useState(1)
  const [maxStep, setMaxStep] = useState(1)

  // Step 1 state
  const [resumeFile, setResumeFile] = useState(null)
  const [resumeId, setResumeId] = useState(null)
  const [lowConfidence, setLowConfidence] = useState(false)

  // Step 2 state (lifted so it survives navigation)
  const [jdText, setJdText] = useState('')
  const [settings, setSettings] = useState(JD_DEFAULTS)
  const [lastAnalyzedJdText, setLastAnalyzedJdText] = useState(null)

  // Analysis results
  const [analysisId, setAnalysisId] = useState(null)
  const [skillMatches, setSkillMatches] = useState([])
  const [rewriteSuggestions, setRewriteSuggestions] = useState([])
  const [debugEvents, setDebugEvents] = useState(null)

  // Resume sections (structured data from upload)
  const [resumeSections, setResumeSections] = useState([])
  const originalSectionsRef = useRef([])

  // Step 4 state (lifted so edits survive navigation)
  const [edits, setEdits] = useState({})
  const [acceptedChanges, setAcceptedChanges] = useState({})

  // Steps 3–5 are stale when jdText has changed since the last analysis run
  const coverageStale = maxStep >= 3 && lastAnalyzedJdText !== null && jdText !== lastAnalyzedJdText
  const staleFrom = coverageStale ? 3 : null

  function handleUploadDone({ resume_id, low_confidence, sections }) {
    setResumeId(resume_id)
    setLowConfidence(low_confidence)
    setResumeSections(sections || [])
    originalSectionsRef.current = JSON.parse(JSON.stringify(sections || []))
    // Clear all analysis state; keep jdText/settings so user doesn't have to re-paste
    setAnalysisId(null)
    setSkillMatches([])
    setRewriteSuggestions([])
    setDebugEvents(null)
    setEdits({})
    setAcceptedChanges({})
    setLastAnalyzedJdText(null)
    setStep(2)
    setMaxStep(2)
  }

  function handleAnalyzeDone({ analysis_id, skill_matches, rewrite_suggestions, debug_events }) {
    setAnalysisId(analysis_id)
    setSkillMatches(skill_matches)
    setRewriteSuggestions(rewrite_suggestions)
    setDebugEvents(debug_events)
    setLastAnalyzedJdText(jdText)
    // Reset step 4/5 state — prior accepted changes are now for a different analysis
    setEdits(Object.fromEntries(rewrite_suggestions.map(s => [s.bullet_id, s.original_text])))
    setAcceptedChanges({})
    setStep(3)
    setMaxStep(3)
  }

  function handleReviewDone() {
    // Build acceptedChanges by diffing current sections against originals
    const changes = {}
    const originals = originalSectionsRef.current
    resumeSections.forEach((section, si) => {
      section.roles.forEach((role, ri) => {
        role.bullets.forEach((bullet, bi) => {
          const origBullet = originals[si]?.roles[ri]?.bullets[bi]
          if (origBullet && bullet.text !== origBullet.text) {
            changes[bullet.bullet_id] = bullet.text
          }
        })
      })
    })
    setAcceptedChanges(changes)
    setStep(5)
    setMaxStep(m => Math.max(m, 5))
  }

  function handleReset() {
    setStep(1)
    setMaxStep(1)
    setResumeFile(null)
    setResumeId(null)
    setLowConfidence(false)
    setResumeSections([])
    originalSectionsRef.current = []
    setJdText('')
    setSettings(JD_DEFAULTS)
    setLastAnalyzedJdText(null)
    setAnalysisId(null)
    setSkillMatches([])
    setRewriteSuggestions([])
    setDebugEvents(null)
    setEdits({})
    setAcceptedChanges({})
  }

  return (
    <div className={step === 4 ? 'app app-wide' : 'app'}>
      <header>
        <h1>Resume ATS Matcher</h1>
        <p className="subtitle">Human-in-the-loop resume tailoring</p>
      </header>

      <StepIndicator
        current={step}
        maxStep={maxStep}
        staleFrom={staleFrom}
        onStepClick={setStep}
      />

      <main>
        {step === 1 && <Step1Upload file={resumeFile} onFileChange={setResumeFile} onDone={handleUploadDone} />}
        {step === 2 && (
          <Step2JD
            resumeId={resumeId}
            lowConfidence={lowConfidence}
            jdText={jdText}
            onJdTextChange={setJdText}
            settings={settings}
            onSettingChange={(key, val) => setSettings(s => ({ ...s, [key]: val }))}
            onDone={handleAnalyzeDone}
          />
        )}
        {step === 3 && (
          <Step3Coverage
            skillMatches={skillMatches}
            debugEvents={debugEvents}
            stale={coverageStale}
            analysisId={analysisId}
            onNext={() => { setStep(4); setMaxStep(m => Math.max(m, 4)) }}
          />
        )}
        {step === 4 && (
          <Step4Edit
            resumeSections={resumeSections}
            skillMatches={skillMatches}
            onSectionsChange={setResumeSections}
            onDone={handleReviewDone}
          />
        )}
        {step === 5 && (
          <Step5Export
            resumeId={resumeId}
            analysisId={analysisId}
            acceptedChanges={acceptedChanges}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  )
}
