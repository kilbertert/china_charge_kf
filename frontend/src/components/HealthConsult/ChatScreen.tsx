import { useRef, useState } from 'react'
import { HealthDisclaimer } from './HealthDisclaimer'

export type ChatMessageItem = {
  id: string
  role: 'user' | 'assistant'
  text?: string
  fileNames?: string[]
}

type Props = {
  messages: ChatMessageItem[]
  loading: boolean
  onSend: (text: string, files: File[]) => void
  errorMessage?: string | null
  onQuickAction?: (key: 'report' | 'symptom' | 'nutrition') => void
}

const QUICK_ACTIONS = [
  { key: 'report' as const, icon: '📄', label: '上传体检报告', prompt: '请上传您的体检报告图片或文字描述' },
  { key: 'symptom' as const, icon: '💬', label: '描述身体不适', prompt: '请描述您目前的身体不适' },
  { key: 'nutrition' as const, icon: '🥗', label: '咨询营养与饮食', prompt: '我想咨询营养与饮食方面的建议' },
]

function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'id-' + Date.now() + '-' + Math.floor(Math.random() * 1e6)
}

export function ChatScreen({ messages, loading, onSend, errorMessage, onQuickAction }: Props) {
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)

  function handleSubmit() {
    const trimmed = text.trim()
    if (!trimmed && files.length === 0) return
    onSend(trimmed, files)
    setText('')
    setFiles([])
    setTimeout(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
    }, 50)
  }

  return (
    <div className="hc-screen hc-chat-screen">
      <div className="hc-welcome-card">
        <div className="hc-avatar-bot">🤖</div>
        <div>
          <div className="hc-welcome-title">您好!我是您的 AI 健康助手</div>
          <div className="hc-welcome-subtitle">可以上传体检报告、描述身体不适,或咨询营养建议</div>
        </div>
      </div>

      <div className="hc-quick-actions">
        {QUICK_ACTIONS.map((q) => (
          <button
            key={q.key}
            type="button"
            className="hc-quick-action"
            onClick={() => {
              setText(q.prompt)
              onQuickAction?.(q.key)
            }}
            disabled={loading}
          >
            <span className="hc-quick-icon">{q.icon}</span>
            <span>{q.label}</span>
          </button>
        ))}
      </div>

      <HealthDisclaimer />

      <div className="hc-message-list" ref={listRef}>
        {messages.length === 0 ? (
          <div className="hc-empty-hint">开始对话吧 ↑</div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`hc-row hc-row-${m.role}`}>
              {m.role === 'assistant' ? <div className="hc-avatar hc-avatar-bot">🤖</div> : null}
              <div className={`hc-bubble hc-bubble-${m.role}`}>
                {m.fileNames && m.fileNames.length > 0 ? (
                  <div className="hc-attached-files">📎 {m.fileNames.join(', ')}</div>
                ) : null}
                {m.text ? <div>{m.text}</div> : null}
              </div>
              {m.role === 'user' ? <div className="hc-avatar hc-avatar-user">我</div> : null}
            </div>
          ))
        )}
        {loading ? (
          <div className="hc-row hc-row-assistant">
            <div className="hc-avatar hc-avatar-bot">🤖</div>
            <div className="hc-bubble hc-bubble-assistant">
              <div className="hc-typing">正在分析…</div>
            </div>
          </div>
        ) : null}
        {errorMessage ? (
          <div className="hc-error-banner">⚠ {errorMessage}</div>
        ) : null}
      </div>

      <div className="hc-composer">
        {files.length > 0 ? (
          <div className="hc-file-chips">
            {files.map((f, i) => (
              <span key={i} className="hc-file-chip">
                📎 {f.name}
                <button type="button" onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}>
                  ✕
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <div className="hc-composer-row">
          <button
            type="button"
            className="hc-add-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            aria-label="添加图片或文件"
          >
            ＋
          </button>
          <textarea
            className="hc-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="请描述您的健康问题或上传报告…"
            rows={1}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit()
              }
            }}
          />
          <button
            type="button"
            className="hc-send-btn"
            onClick={handleSubmit}
            disabled={loading || (!text.trim() && files.length === 0)}
          >
            发送
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,application/pdf"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => {
            const picked = Array.from(e.target.files ?? [])
            if (picked.length) setFiles((prev) => [...prev, ...picked])
            e.currentTarget.value = ''
          }}
        />
        <div className="hc-privacy-hint">
          对话内容仅用于 AI 分析,不会用于其他用途。
        </div>
      </div>
    </div>
  )
}

export function newChatMessage(
  role: 'user' | 'assistant',
  payload: { text?: string; fileNames?: string[] },
): ChatMessageItem {
  return { id: generateId(), role, ...payload }
}
