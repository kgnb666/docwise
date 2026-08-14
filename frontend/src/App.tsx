import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import {
  deleteDoc,
  fetchDocChunks,
  fetchDocs,
  fetchStats,
  fetchSystemInfo,
  streamChat,
  uploadDoc,
  type DocChunk,
  type SystemInfo,
} from './api'
import type { ChatMessage, Citation, DocInfo, ToolCall } from './types'
import './styles.css'

const STORAGE_KEY = 'docwise.messages.v1'

/** 从 localStorage 恢复历史会话（刷新不丢）。 */
function loadMessages(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

/** Markdown 渲染（DOMPurify 消毒防 XSS）。 */
function Markdown({ text }: { text: string }) {
  const html = useMemo(() => DOMPurify.sanitize(marked.parse(text) as string), [text])
  return <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages)
  // 每条消息当前展开的引用片段（chunk_id）；null 表示未展开
  const [expanded, setExpanded] = useState<Record<number, string | null>>({})
  // 文档分块查看弹层
  const [chunkView, setChunkView] = useState<{ docName: string; chunks: DocChunk[] } | null>(null)
  const [chunkLoading, setChunkLoading] = useState(false)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [stats, setStats] = useState({ documents: 0, chunks: 0 })
  const [sysInfo, setSysInfo] = useState<SystemInfo | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const refreshDocs = useCallback(async () => {
    const [docList, st] = await Promise.all([fetchDocs(), fetchStats()])
    setDocs(docList)
    setStats(st)
  }, [])

  useEffect(() => {
    refreshDocs()
  }, [refreshDocs])

  useEffect(() => {
    // 系统配置概览（模型 / 分词），失败静默
    fetchSystemInfo()
      .then(setSysInfo)
      .catch(() => {})
  }, [])

  useEffect(() => {
    // 会话持久化：每次消息变化都保存
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    } catch {
      // 存储不可用时静默降级（隐私模式等）
    }
  }, [messages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const query = input.trim()
    if (!query || streaming) return
    setInput('')

    const history = [...messages]
    setMessages([...history, { role: 'user', content: query }])
    setStreaming(true)

    let acc = ''
    let citations: Citation[] = []
    const toolCalls: ToolCall[] = []
    let rewrittenNote = ''
    // 预置一个空的 assistant 消息，流式内容往里填
    setMessages([...history, { role: 'user', content: query }, { role: 'assistant', content: '', citations: [], toolCalls: [] }])

    const patch = (content: string, cites: Citation[], tools: ToolCall[], rewritten?: string) => {
      setMessages((msgs) => {
        const copy = [...msgs]
        copy[copy.length - 1] = { role: 'assistant', content, citations: cites, toolCalls: tools, rewritten }
        return copy
      })
    }

    try {
      await streamChat(query, history, {
        onCitations: (c) => {
          citations = c
          patch(acc, citations, [...toolCalls], rewrittenNote || undefined)
        },
        onDelta: (d) => {
          acc += d
          patch(acc, citations, [...toolCalls], rewrittenNote || undefined)
        },
        onToolResult: (name, result) => {
          toolCalls.push({ name, result })
          patch(acc, citations, [...toolCalls], rewrittenNote || undefined)
        },
        onQueryRewritten: (_original, rewritten) => {
          rewrittenNote = rewritten
          patch(acc, citations, [...toolCalls], rewritten)
        },
        onError: (msg) => {
          acc += `\n\n> ⚠️ ${msg}`
          patch(acc, citations, [...toolCalls], rewrittenNote || undefined)
        },
      })
    } finally {
      setStreaming(false)
    }
  }

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await uploadDoc(file)
      await refreshDocs()
    } catch (err) {
      alert(err instanceof Error ? err.message : '上传失败')
    }
    e.target.value = ''
  }

  async function handleDelete(docId: string) {
    await deleteDoc(docId)
    await refreshDocs()
  }

  async function handleViewChunks(doc: DocInfo) {
    setChunkLoading(true)
    try {
      const chunks = await fetchDocChunks(doc.doc_id)
      setChunkView({ docName: doc.name, chunks })
    } catch {
      setChunkView({ docName: doc.name, chunks: [] })
    } finally {
      setChunkLoading(false)
    }
  }

  return (
    <div className="layout">
      {/* 左侧：文档管理 */}
      <aside className="sidebar">
        <h1 className="logo">📚 DocWise</h1>
        <p className="subtitle">智能知识库问答与 Agent 助手</p>

        <div className="sidebar-actions">
          <label className="upload-btn">
            📤 上传文档（txt / md / pdf）
            <input type="file" accept=".txt,.md,.markdown,.pdf" hidden onChange={handleUpload} />
          </label>
          <button className="clear-btn" onClick={() => setMessages([])} title="清空对话">
            🗑 清空
          </button>
        </div>

        <div className="stats">
          <span>📄 文档 {stats.documents}</span>
          <span>🧩 分块 {stats.chunks}</span>
        </div>

        <ul className="doc-list">
          {docs.length === 0 && <li className="doc-empty">还没有文档，先上传几份试试</li>}
          {docs.map((doc) => (
            <li key={doc.doc_id} className="doc-item">
              <div className="doc-info">
                <span className="doc-name" title={doc.name}>{doc.name}</span>
                <span className="doc-meta">{doc.chunk_count} 块 · {doc.created_at}</span>
              </div>
              <div className="doc-actions">
                <button className="doc-view" onClick={() => handleViewChunks(doc)} title="查看分块">
                  🧩
                </button>
                <button className="doc-delete" onClick={() => handleDelete(doc.doc_id)} title="删除">
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>

        <div className="sidebar-footer">
          <p>💡 提示：先上传文档，再提问。回答会标注引用来源。</p>
          {sysInfo && (
            <div className="sys-info">
              <span>🤖 {sysInfo.config.llm_model}</span>
              <span>🧠 {sysInfo.config.embedding_provider === 'hash' ? '离线哈希嵌入' : sysInfo.config.embedding_model}</span>
              <span>✂️ 分词：{sysInfo.config.tokenizer}</span>
              <span>🤖 Agent：{sysInfo.config.agent_enabled ? '开' : '关'}</span>
            </div>
          )}
        </div>
      </aside>

      {/* 右侧：聊天 */}
      <main className="chat">
        <div className="chat-body">
          {messages.length === 0 && (
            <div className="welcome">
              <h2>你好，我是 DocWise 👋</h2>
              <p>上传你的文档，然后向我提问。我会基于知识库回答，并标注引用来源。</p>
              <p className="welcome-examples">试试问：「总结一下知识库里关于 XX 的内容」</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`msg msg-${msg.role}`}>
              <div className="msg-bubble">
                {msg.role === 'assistant' ? (
                  msg.content ? <Markdown text={msg.content} /> : streaming && i === messages.length - 1 ? '…' : ''
                ) : (
                  msg.content
                )}
              </div>
              {msg.role === 'assistant' && msg.rewritten && (
                <div className="rewritten-note">🔄 已将追问改写为：「{msg.rewritten}」用于检索</div>
              )}
              {msg.role === 'assistant' && msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="tool-calls">
                  {msg.toolCalls.map((t, idx) => (
                    <span key={idx} className="tool-call" title={t.result}>
                      🔧 调用了 {t.name}
                    </span>
                  ))}
                </div>
              )}
              {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                <div className="citations">
                  {msg.citations.map((c) => (
                    <button
                      key={c.chunk_id}
                      className="citation"
                      title="点击查看完整片段"
                      onClick={() =>
                        setExpanded((prev) => ({ ...prev, [i]: prev[i] === c.chunk_id ? null : c.chunk_id }))
                      }
                    >
                      📖 {c.doc_name} · 片段{c.index} · 相似度 {c.score.toFixed(2)}
                    </button>
                  ))}
                </div>
              )}
              {msg.role === 'assistant' && expanded[i] && (
                <div className="citation-detail">
                  {msg.citations?.find((c) => c.chunk_id === expanded[i])?.text ?? ''}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="chat-input-bar">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder={streaming ? '正在生成…' : '输入问题，Enter 发送，Shift+Enter 换行'}
            rows={2}
            disabled={streaming}
          />
          <button className="send-btn" onClick={handleSend} disabled={streaming || !input.trim()}>
            {streaming ? '…' : '发送'}
          </button>
        </div>
      </main>

      {/* 文档分块查看弹层 */}
      {chunkView && (
        <div className="modal-overlay" onClick={() => setChunkView(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span>🧩 《{chunkView.docName}》的分块（{chunkView.chunks.length} 块）</span>
              <button className="modal-close" onClick={() => setChunkView(null)}>✕</button>
            </div>
            <div className="modal-body">
              {chunkLoading && <p className="modal-hint">加载中…</p>}
              {!chunkLoading && chunkView.chunks.length === 0 && (
                <p className="modal-hint">暂无分块（文档可能太短或为空）</p>
              )}
              {chunkView.chunks.map((c) => (
                <div key={c.chunk_id} className="chunk-item">
                  <span className="chunk-index">#{c.index}</span>
                  <span className="chunk-text">{c.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
