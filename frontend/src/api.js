const API_BASE = '/api'

export async function fetchDigest(city, simpleMode) {
  const resp = await fetch(`${API_BASE}/digest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ city, simple_mode: simpleMode }),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export async function sendChat(message, city, simpleMode, chatHistory = []) {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      city,
      simple_mode: simpleMode,
      chat_history: chatHistory,
    }),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export async function updateReportStatus(reportId, status) {
  const resp = await fetch(`${API_BASE}/reports/${reportId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
  return resp.json()
}

export async function checkHealth() {
  const resp = await fetch(`${API_BASE}/health`)
  return resp.json()
}
