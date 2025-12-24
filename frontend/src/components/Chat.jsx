import React, { useEffect, useRef, useState } from 'react'
import { sendMessage } from '../api/client.js'
import Message from './Message.jsx'

export default function Chat() {
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const listRef = useRef(null)
    const textareaRef = useRef(null)
    const suggestions = [
        'What are the key cybersecurity threats today?',
        'Explain zero trust architecture',
        'How to secure a home network?',
        'How to prevent phishing attacks?'
    ]

    useEffect(() => {
        if (!listRef.current) return
        listRef.current.scrollTop = listRef.current.scrollHeight
    }, [messages])

    const handleSend = async () => {
        const text = input.trim()
        if (!text || loading) return
        setInput('')
        setError(null)

        const nextMessages = [...messages, { role: 'user', content: text }]
        setMessages(nextMessages)

        setLoading(true)
        try {
            const reply = await sendMessage(text)
            setMessages([...nextMessages, { role: 'assistant', content: reply }])
        } catch (e) {
            console.error(e)
            setError(e?.message || 'Failed to get response')
        } finally {
            setLoading(false)
        }
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
        setInput(text)
        await handleSend()
    }

    return (
        <div className="chat">
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
    )
}
