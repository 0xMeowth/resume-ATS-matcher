const BASE = '/api'

async function checkResponse(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res
}

export async function uploadResume(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await checkResponse(await fetch(`${BASE}/resume`, { method: 'POST', body: form }))
  return res.json()
}

export async function analyzeJD(resumeId, jdText, settings) {
  const res = await checkResponse(await fetch(`${BASE}/jd/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_id: resumeId, jd_text: jdText, settings }),
  }))
  return res.json()
}

export async function submitFeedback(analysisId, skillPhrase, bulletText, label) {
  await fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analysis_id: analysisId,
      skill_phrase: skillPhrase,
      bullet_text: bulletText,
      label,
    }),
  })
}

export async function exportPdf(sections) {
  const res = await checkResponse(await fetch(`${BASE}/export/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sections }),
  }))
  return res.blob()
}
