import React, { useState, useRef } from 'react'
import { uploadResume } from '../api'

export default function Step1Upload({ file, onFileChange, onDone }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

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

  function handleFile(f) {
    if (f && (f.name.endsWith('.pdf') || f.name.endsWith('.docx'))) {
      onFileChange(f)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  return (
    <div className="step">
      <h2>1) Upload resume</h2>
      <form onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="file"
          accept=".docx,.pdf"
          onChange={e => handleFile(e.target.files[0] || null)}
          style={{ display: 'none' }}
        />
        <div
          className={`dropzone${dragOver ? ' dropzone-active' : ''}${file ? ' dropzone-has-file' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          {file ? (
            <span className="dropzone-filename">{file.name}</span>
          ) : (
            <>
              <span className="dropzone-icon">+</span>
              <span className="dropzone-label">Drop your resume here or click to browse</span>
              <span className="dropzone-hint">.pdf or .docx</span>
            </>
          )}
        </div>
        <button type="submit" disabled={!file || loading}>
          {loading ? 'Parsing...' : 'Upload & parse'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
