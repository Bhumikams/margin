const BASE = import.meta.env.VITE_API_URL || '/api'

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(BASE + path, options)
  } catch {
    throw new Error("Can't reach the server. Start the backend with `uvicorn app.main:app --reload`.")
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* not JSON */ }
    throw new Error(detail)
  }
  return res.json()
}

const json = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => request('/health'),
  subjects: () => request('/subjects'),
  documents: () => request('/documents'),
  deleteDocument: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
  upload: (file, subject, module) => {
    const form = new FormData()
    form.append('file', file)
    form.append('subject', subject)
    if (module) form.append('module', module)
    return request('/upload', { method: 'POST', body: form })
  },
  ask: (body) => request('/ask', json(body)),
  quiz: (body) => request('/quiz', json(body)),
  summarize: (body) => request('/summarize', json(body)),
}

export function scopeLabel(scope) {
  if (!scope.subject) return 'All notes'
  return scope.module ? `${scope.subject}, Module ${scope.module}` : scope.subject
}

export function pageLabel(s) {
  return s.page_start === s.page_end ? `p. ${s.page_start}` : `pp. ${s.page_start}–${s.page_end}`
}
