const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function createNewSession() {
  const url = `${baseURL}/api/new-session`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Failed to create session`)
  }

  const data = await res.json()
  return data?.session_id
}

export async function sendMessage(question, sessionId = null) {
  const url = `${baseURL}/api/chat`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ 
      question,
      session_id: sessionId
    })
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Request failed`)
  }

  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = await res.json()
    return {
      answer: data?.answer || data?.content || JSON.stringify(data),
      session_id: data?.session_id
    }
  }
  // Fallback to text
  return {
    answer: await res.text()
  }
}
