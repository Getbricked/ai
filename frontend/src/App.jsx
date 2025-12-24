import React from 'react'
import Chat from './components/Chat.jsx'

export default function App() {
    return (
        <div className="app">
            <header className="app-header">
                <h1>Cybersecurity AI Assistant</h1>
                <p className="subtitle">Ask questions and get answers about cybersecurity</p>
            </header>
            <main className="app-main">
                <Chat />
            </main>
            <footer className="app-footer">
                <span>Version: <code>0.1.0</code></span>
            </footer>
        </div>
    )
}
