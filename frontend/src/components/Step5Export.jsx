import React, { useState } from 'react'
import { exportPdf } from '../api'

export default function Step5Export({ resumeSections, acceptedChanges, onReset }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [pdfUrl, setPdfUrl] = useState(null)

  async function handleExport() {
    setLoading(true)
    setError(null)
    try {
      const blob = await exportPdf(resumeSections)
      const url = URL.createObjectURL(blob)
      setPdfUrl(url)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleDownload() {
    if (!pdfUrl) return
    const a = document.createElement('a')
    a.href = pdfUrl
    a.download = 'tailored_resume.pdf'
    a.click()
  }

  const changeCount = Object.keys(acceptedChanges).length

  return (
    <div className="step">
      <h2>5) Export tailored resume</h2>
      <p>{changeCount} change{changeCount !== 1 ? 's' : ''} applied to the resume.</p>

      {!pdfUrl && (
        <button onClick={handleExport} disabled={loading}>
          {loading ? 'Generating PDF...' : 'Generate PDF preview'}
        </button>
      )}

      {pdfUrl && (
        <>
          <div className="pdf-preview">
            <iframe src={pdfUrl} title="Resume PDF preview" />
          </div>
          <div className="pdf-actions">
            <button onClick={handleDownload}>Download PDF</button>
            <button className="secondary-btn" onClick={() => { URL.revokeObjectURL(pdfUrl); setPdfUrl(null) }}>
              Regenerate
            </button>
          </div>
        </>
      )}

      {error && <p className="error">{error}</p>}

      <hr />
      <button className="secondary-btn" onClick={onReset}>Start over</button>
    </div>
  )
}
