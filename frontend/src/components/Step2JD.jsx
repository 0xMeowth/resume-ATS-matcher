import React, { useState } from 'react'
import { analyzeJD } from '../api'

export default function Step2JD({ resumeId, lowConfidence, jdText, onJdTextChange, settings, onSettingChange, onDone }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showSettings, setShowSettings] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!jdText.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await analyzeJD(resumeId, jdText, settings)
      onDone(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="step">
      <h2>2) Job description</h2>
      {lowConfidence && (
        <p className="warning">PDF input: parsing accuracy may be lower than .docx. Export will produce a .docx.</p>
      )}
      <form onSubmit={handleSubmit}>
        <textarea
          rows={10}
          placeholder="Paste job description text here…"
          value={jdText}
          onChange={e => onJdTextChange(e.target.value)}
        />

        <button type="button" className="link-btn" onClick={() => setShowSettings(s => !s)}>
          {showSettings ? '▲ Hide settings' : '▼ Settings'}
        </button>

        {showSettings && (
          <div className="settings-grid">
            <label>Max skill terms
              <input type="number" min={10} max={300} value={settings.max_skill_terms}
                onChange={e => onSettingChange('max_skill_terms', Number(e.target.value))} />
            </label>

            <label>Skill ranker
              <select value={settings.skill_ranker} onChange={e => onSettingChange('skill_ranker', e.target.value)}>
                <option value="mmr">MMR (embeddings)</option>
                <option value="tfidf">TF-IDF</option>
                <option value="hybrid">Hybrid (TF-IDF + MMR)</option>
              </select>
            </label>

            {(settings.skill_ranker === 'mmr' || settings.skill_ranker === 'hybrid') && (
              <label>MMR diversity ({settings.mmr_diversity})
                <input type="range" min={0} max={0.9} step={0.05} value={settings.mmr_diversity}
                  onChange={e => onSettingChange('mmr_diversity', Number(e.target.value))} />
              </label>
            )}

            <label>Matching strategy
              <select value={settings.skill_matching} onChange={e => onSettingChange('skill_matching', e.target.value)}>
                <option value="embedding">Embedding</option>
                <option value="tfidf_rerank">TF-IDF shortlist + Embedding</option>
              </select>
            </label>

            {settings.skill_matching === 'tfidf_rerank' && (
              <label>TF-IDF shortlist size
                <input type="number" min={5} max={50} value={settings.rerank_top_k}
                  onChange={e => onSettingChange('rerank_top_k', Number(e.target.value))} />
              </label>
            )}

            <label>Strong match threshold ({settings.skill_strong_threshold})
              <input type="range" min={0.5} max={0.95} step={0.05} value={settings.skill_strong_threshold}
                onChange={e => onSettingChange('skill_strong_threshold', Number(e.target.value))} />
            </label>

            <label>Weak match threshold ({settings.skill_weak_threshold})
              <input type="range" min={0.3} max={0.9} step={0.05} value={settings.skill_weak_threshold}
                onChange={e => onSettingChange('skill_weak_threshold', Number(e.target.value))} />
            </label>

            <label>
              <input type="checkbox" checked={settings.debug}
                onChange={e => onSettingChange('debug', e.target.checked)} />
              {' '}Debug skill extraction
            </label>
          </div>
        )}

        <button type="submit" disabled={!jdText.trim() || loading}>
          {loading ? 'Analyzing…' : 'Analyze JD'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
