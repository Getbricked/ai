import { v4 as uuidv4 } from 'uuid'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Load all saved sessions from localStorage
export function loadAllSessions() {
  try {
    const data = localStorage.getItem('chat_sessions')
    return data ? JSON.parse(data) : []
  } catch (error) {
    console.error('Failed to load sessions:', error)
    return []
  }
}

// Save a session to localStorage
export function saveSession(sessionData) {
  try {
    const sessions = loadAllSessions()
    const existingIndex = sessions.findIndex(s => s.session_id === sessionData.session_id)
    
    if (existingIndex >= 0) {
      sessions[existingIndex] = sessionData
    } else {
      sessions.push(sessionData)
    }
    
    localStorage.setItem('chat_sessions', JSON.stringify(sessions))
    return true
  } catch (error) {
    console.error('Failed to save session:', error)
    return false
  }
}

// Save session to backend (disk)
export async function saveSessionToDisk(sessionData) {
  try {
    const response = await fetch(`${baseURL}/api/save-session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(sessionData)
    })
    
    if (!response.ok) {
      const error = await response.text()
      console.error('Failed to save session to disk:', error)
      return false
    }
    
    return true
  } catch (error) {
    console.error('Failed to save session to disk:', error)
    return false
  }
}

// Create a new session object from current messages
export function createSessionObject(sessionId, messages, userId = 'user_default') {
  const now = new Date().toISOString()
  
  const sessionObject = {
    session_id: sessionId || uuidv4(),
    user_id: userId,
    created_at: now,
    updated_at: now,
    messages: messages.map((msg, index) => ({
      role: msg.role,
      content: msg.content,
      timestamp: new Date(new Date(now).getTime() + index * 1000).toISOString()
    }))
  }
  
  return sessionObject
}

// Get a session by ID
export function getSessionById(sessionId) {
  const sessions = loadAllSessions()
  return sessions.find(s => s.session_id === sessionId)
}

// Delete a session
export function deleteSession(sessionId) {
  try {
    const sessions = loadAllSessions()
    const filtered = sessions.filter(s => s.session_id !== sessionId)
    localStorage.setItem('chat_sessions', JSON.stringify(filtered))
    return true
  } catch (error) {
    console.error('Failed to delete session:', error)
    return false
  }
}
