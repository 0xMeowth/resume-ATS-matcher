import React, { useState } from 'react'
import { exportResume } from '../api'

export default function Step5Export({ resumeId, analysisId, acceptedChanges, onReset }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [downloaded, setDownloaded] = useState(false)

  async function handleExport() {
    setLoading(true)
    setError(null)
    try {
      const blob = await exportResume(resumeId, analysisId, acceptedChanges)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'tailored_resume.docx'
      a.click()
      URL.revokeObjectURL(url)
      setDownloaded(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const changeCount = Object.keys(acceptedChanges).length

  return (
    <div className="step">
      <h2>5) Export tailored resume</h2>
      <p>{changeCount} change{changeCount !== 1 ? 's' : ''} applied to the resume.</p>
      <p className="muted">Export format: .docx (regardless of input format)</p>

      <button onClick={handleExport} disabled={loading}>
        {loading ? 'Generating…' : 'Download tailored .docx'}
      </button>

      {downloaded && <p className="success">Downloaded! Start a new session below.</p>}
      {error && <p className="error">{error}</p>}

      <hr />
      <button className="secondary-btn" onClick={onReset}>Start over</button>
    </div>
  )
}
