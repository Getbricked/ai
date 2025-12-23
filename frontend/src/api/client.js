const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function sendMessage(question) {
  const url = `${baseURL}/api/chat`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ question })
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Request failed (${res.status})`)
  }

  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = await res.json()
    return data?.answer || data?.content || JSON.stringify(data)
  }
  // Fallback to text
  return await res.text()
}
