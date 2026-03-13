import React, { useState } from 'react'
import { uploadResume } from '../api'

export default function Step1Upload({ file, onFileChange, onDone }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const data = await uploadResume(file)
      onDone(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="step">
      <h2>1) Upload resume</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="file"
          accept=".docx,.pdf"
          onChange={e => onFileChange(e.target.files[0] || null)}
        />
        {file && <p className="muted">Selected: {file.name}</p>}
        <button type="submit" disabled={!file || loading}>
          {loading ? 'Parsing…' : 'Upload & parse'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
