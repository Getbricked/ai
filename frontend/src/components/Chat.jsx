import React, { useEffect, useRef, useState } from 'react'
import { sendMessage, createNewSession } from '../api/client.js'
import { loadAllSessions, saveSession, saveSessionToDisk, createSessionObject, getSessionById, deleteSession } from '../api/sessions.js'
import Message from './Message.jsx'
import SessionSidebar from './SessionSidebar.jsx'

export default function Chat() {
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [sessionId, setSessionId] = useState(null)
    const [savedSessions, setSavedSessions] = useState([])
    const [currentSessionTitle, setCurrentSessionTitle] = useState('New Chat')
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true)
    const listRef = useRef(null)
    const textareaRef = useRef(null)
    const suggestions = [
        'What are the key cybersecurity threats today?',
        'How to reduce the risk of ransomware?',
        'How to secure a home network?',
        'How to prevent phishing attacks?'
    ]

    // Load saved sessions on mount
    useEffect(() => {
        const sessions = loadAllSessions()
        setSavedSessions(sessions)
    }, [])

    // On page reload/close, persist current session locally only
    useEffect(() => {
        const handleBeforeUnload = () => {
            if (messages.length > 0 && sessionId) {
                const sessionObject = createSessionObject(sessionId, messages)
                // Fire-and-forget; beforeunload cannot await async work
                saveSession(sessionObject)
            }
        }

        window.addEventListener('beforeunload', handleBeforeUnload)
        return () => window.removeEventListener('beforeunload', handleBeforeUnload)
    }, [messages, sessionId])

    useEffect(() => {
        if (!listRef.current) return
        listRef.current.scrollTop = listRef.current.scrollHeight
    }, [messages])

    const initializeSession = async () => {
        try {
            const newSessionId = await createNewSession()
            setSessionId(newSessionId)
        } catch (e) {
            console.error('Failed to create session:', e)
            setError('Failed to initialize chat session')
        }
    }

    useEffect(() => {
        initializeSession()
    }, [])

    const handleSend = async () => {
        const text = input.trim()
        if (!text || loading) return
        setInput('')
        setError(null)

        const nextMessages = [...messages, { role: 'user', content: text }]
        setMessages(nextMessages)

        setLoading(true)
        try {
            const response = await sendMessage(text, sessionId)
            const newSessionId = response.session_id || sessionId
            setSessionId(newSessionId)
            setMessages([...nextMessages, { role: 'assistant', content: response.answer }])
        } catch (e) {
            console.error(e)
            setError(e?.message || 'Failed to get response')
        } finally {
            setLoading(false)
        }
    }

    const handleNewChat = async () => {
        // Save current session if it has messages
        if (messages.length > 0 && sessionId) {
            const sessionObject = createSessionObject(sessionId, messages)
            saveSession(sessionObject)

            // Also save to backend (disk, i.e. frontend/sessions)
            try {
                await saveSessionToDisk(sessionObject)
            } catch (err) {
                console.error('Failed to save session on new chat:', err)
            }

            // Update saved sessions list
            const updatedSessions = loadAllSessions()
            setSavedSessions(updatedSessions)
        }

        // Reset chat
        setMessages([])
        setInput('')
        setError(null)
        setCurrentSessionTitle('New Chat')
        initializeSession()
    }

    const handleLoadSession = (session) => {
        // Save current session if it has messages
        if (messages.length > 0 && sessionId) {
            const sessionObject = createSessionObject(sessionId, messages)
            saveSession(sessionObject)

            // Also save to backend (disk)
            saveSessionToDisk(sessionObject)
        }

        // Load selected session
        setMessages(session.messages)
        setSessionId(session.session_id)
        setInput('')
        setError(null)

        // Set title based on first user message
        const firstUserMsg = session.messages.find(m => m.role === 'user')
        if (firstUserMsg) {
            setCurrentSessionTitle(firstUserMsg.content.substring(0, 30) + (firstUserMsg.content.length > 30 ? '...' : ''))
        }
    }

    const handleDeleteSession = async (e, sessionIdToDelete) => {
        e.stopPropagation()

        // Save the session to disk before deleting it
        const sessionToDelete = getSessionById(sessionIdToDelete)
        if (sessionToDelete) {
            try {
                await saveSessionToDisk(sessionToDelete)
            } catch (err) {
                console.error('Failed to save session before delete:', err)
            }
        }

        deleteSession(sessionIdToDelete)
        const updatedSessions = loadAllSessions()
        setSavedSessions(updatedSessions)
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    const handleInputChange = (e) => {
        setInput(e.target.value)
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto'
            textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px'
        }
    }

    const handleChip = async (text) => {
        // We need to handle this differently since state is async
        const nextMessages = [...messages, { role: 'user', content: text }]
        setMessages(nextMessages)

        setLoading(true)
        try {
            const response = await sendMessage(text, sessionId)
            const newSessionId = response.session_id || sessionId
            setSessionId(newSessionId)
            setMessages([...nextMessages, { role: 'assistant', content: response.answer }])
        } catch (e) {
            console.error(e)
            setError(e?.message || 'Failed to get response')
        } finally {
            setLoading(false)
        }
    }

    const handleToggleSidebar = () => {
        setIsSidebarCollapsed(prev => !prev)
    }

    return (
        <div className={`chat-container ${isSidebarCollapsed ? 'collapsed' : ''}`}>
            <SessionSidebar
                savedSessions={savedSessions}
                onNewChat={handleNewChat}
                onLoadSession={handleLoadSession}
                onDeleteSession={handleDeleteSession}
                isCollapsed={isSidebarCollapsed}
            />

            {/* Main Chat */}
            <div className="chat">
                <div className="chat-header">
                    <button
                        className="toggle-sidebar-btn"
                        onClick={handleToggleSidebar}
                        title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                    >
                        ☰
                    </button>
                    <div className="chat-header-text">
                        <h2>Cybersecurity AI Assistant</h2>
                        <p className="chat-header-subtitle">Ask questions and get answers about cybersecurity</p>
                    </div>
                </div>
                <div className="messages" ref={listRef}>
                    <div className="messages-inner">
                        {messages.length === 0 ? (
                            <>
                                <section className="hero">
                                    <h2 className="hero-title">Tired of searching for cybersecurity documents? Here is your AI assistant!</h2>
                                    <div className="prompt-bar">
                                        <div className="prompt-controls">
                                        </div>
                                        <input
                                            className="prompt-input"
                                            type="text"
                                            placeholder="Ask Assistant"
                                            value={input}
                                            onChange={(e) => setInput(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') handleSend()
                                            }}
                                        />
                                        <div className="prompt-actions">
                                            <button
                                                className="prompt-send"
                                                disabled={loading || !input.trim()}
                                                onClick={handleSend}
                                            >
                                                ➤
                                            </button>
                                        </div>
                                    </div>
                                </section>
                                <div className="chips">
                                    {suggestions.map((s, i) => (
                                        <button className="chip" key={i} onClick={() => handleChip(s)}>{s}</button>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <>
                                {messages.map((m, i) => (
                                    <Message key={i} role={m.role} content={m.content} />
                                ))}
                                {loading && <Message role="assistant" content="Thinking…" pending />}
                            </>
                        )}
                    </div>
                </div>

                {messages.length > 0 && (
                    <div className="composer">
                        <div className="composer-inner">
                            <textarea
                                ref={textareaRef}
                                placeholder="Ask anything about cybersecurity"
                                value={input}
                                onChange={handleInputChange}
                                onKeyDown={handleKeyDown}
                                rows={1}
                            />
                            <button className="send" disabled={loading || !input.trim()} onClick={handleSend}>
                                ➤
                            </button>
                        </div>
                    </div>
                )}

                {error && <div className="error">{error}</div>}
            </div>
        </div>
    )
}
