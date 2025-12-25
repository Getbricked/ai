import React from 'react'

export default function SessionSidebar({ savedSessions, onNewChat, onLoadSession, onDeleteSession, isCollapsed }) {
    return (
        <aside className={`chat-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
            <div className="sidebar-header">
                <button className="new-chat-btn" onClick={onNewChat}>
                    {isCollapsed ? '+' : '+ New Chat'}
                </button>
            </div>

            {!isCollapsed && savedSessions.length > 0 && (
                <div className="sessions-list">
                    <h3 className="sessions-title">Recent Chats</h3>
                    <ul>
                        {savedSessions.map((session) => (
                            <li key={session.session_id}>
                                <button
                                    className="session-item"
                                    onClick={() => onLoadSession(session)}
                                    title={session.messages.find(m => m.role === 'user')?.content}
                                >
                                    <span className="session-name">
                                        {session.messages.find(m => m.role === 'user')?.content?.substring(0, 25) || 'Untitled'}
                                        {session.messages.find(m => m.role === 'user')?.content?.length > 25 ? '...' : ''}
                                    </span>
                                </button>
                                <button
                                    className="delete-session-btn"
                                    onClick={(e) => onDeleteSession(e, session.session_id)}
                                    title="Delete session"
                                >
                                    ×
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </aside>
    )
}
