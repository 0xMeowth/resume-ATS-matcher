import React, { useState } from 'react'
import Step1Upload from './components/Step1Upload'
import Step2JD from './components/Step2JD'
import Step3Coverage from './components/Step3Coverage'
import Step4Review from './components/Step4Review'
import Step5Export from './components/Step5Export'

const STEPS = ['Upload', 'Job Description', 'Coverage', 'Review', 'Export']

function StepIndicator({ current }) {
  return (
    <div className="step-indicator">
      {STEPS.map((label, i) => (
        <div key={i} className={`step-dot ${i + 1 === current ? 'active' : i + 1 < current ? 'done' : ''}`}>
          <span className="dot">{i + 1 < current ? '✓' : i + 1}</span>
          <span className="dot-label">{label}</span>
        </div>
      ))}
    </div>
  )
}

export default function App() {
  const [step, setStep] = useState(1)
  const [resumeId, setResumeId] = useState(null)
  const [lowConfidence, setLowConfidence] = useState(false)
  const [analysisId, setAnalysisId] = useState(null)
  const [skillMatches, setSkillMatches] = useState([])
  const [rewriteSuggestions, setRewriteSuggestions] = useState([])
  const [debugEvents, setDebugEvents] = useState(null)
  const [acceptedChanges, setAcceptedChanges] = useState({})

  function handleUploadDone({ resume_id, low_confidence }) {
    setResumeId(resume_id)
    setLowConfidence(low_confidence)
    setStep(2)
  }

  function handleAnalyzeDone({ analysis_id, skill_matches, rewrite_suggestions, debug_events }) {
    setAnalysisId(analysis_id)
    setSkillMatches(skill_matches)
    setRewriteSuggestions(rewrite_suggestions)
    setDebugEvents(debug_events)
    setStep(3)
  }

  function handleReviewDone(changes) {
    setAcceptedChanges(changes)
    setStep(5)
  }

  function handleReset() {
    setStep(1)
    setResumeId(null)
    setLowConfidence(false)
    setAnalysisId(null)
    setSkillMatches([])
    setRewriteSuggestions([])
    setDebugEvents(null)
    setAcceptedChanges({})
  }

  return (
    <div className="app">
      <header>
        <h1>Resume ATS Matcher</h1>
        <p className="subtitle">Human-in-the-loop resume tailoring</p>
      </header>

      <StepIndicator current={step} />

      <main>
        {step === 1 && <Step1Upload onDone={handleUploadDone} />}
        {step === 2 && (
          <Step2JD
            resumeId={resumeId}
            lowConfidence={lowConfidence}
            onDone={handleAnalyzeDone}
          />
        )}
        {step === 3 && (
          <Step3Coverage
            skillMatches={skillMatches}
            debugEvents={debugEvents}
            onNext={() => setStep(4)}
          />
        )}
        {step === 4 && (
          <Step4Review
            suggestions={rewriteSuggestions}
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
