import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'

export default function Message({ role, content, pending = false }) {
    return (
        <div className={`message ${role}`}>
            <div className="avatar" aria-hidden>
                {role === 'assistant' ? '🛡️' : ''}
            </div>
            <div className="bubble">
                {pending ? (
                    <span className="pending">{content}</span>
                ) : (
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeHighlight]}
                        components={{
                            a: ({ node, ...props }) => (
                                <a {...props} target="_blank" rel="noopener noreferrer" />
                            ),
                        }}
                    >
                        {content}
                    </ReactMarkdown>
                )}
            </div>
        </div>
    )
}
