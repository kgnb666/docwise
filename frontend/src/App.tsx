import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type MouseEvent } from 'react'
import DOMPurify from 'dompurify'
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
import { linkifyCitationRefs, marked } from './markdown'
import {
  loadSessions,
  newSession,
  saveSessions,
  sessionTitle,
  timeLabel,
  ACTIVE_KEY,
  type ChatSession,
} from './sessions'
import './styles.css'

/** Markdown 渲染：DOMPurify 消毒防 XSS；回答中的 [1]/[2] 引用序号转为按钮；代码块自带复制与语法高亮。 */
function Markdown({ text, onRefClick }: { text: string; onRefClick?: (n: number) => void }) {
  const html = useMemo(() => {
    const clean = DOMPurify.sanitize(marked.parse(text) as string, {
      ADD_ATTR: ['data-ref'],
      ADD_TAGS: ['button'],
    })
    return linkifyCitationRefs(clean)
  }, [text])

  const handleClick = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement

    // 1) 引用气泡高亮
    const refEl = target.closest('.ref-chip')
    if (refEl && onRefClick) {
      onRefClick(Number(refEl.getAttribute('data-ref')))
      return
    }

    // 2) 代码块一键复制
    const copyBtn = target.closest<HTMLButtonElement>('.code-copy-btn')
    if (copyBtn) {
      const wrapper = copyBtn.closest('.code-block-wrapper')
      const codeEl = wrapper?.querySelector('pre code')
      const codeText = codeEl?.textContent ?? ''
      if (codeText) {
        const copySuccess = () => {
          copyBtn.textContent = '✅ 已复制'
          copyBtn.classList.add('copied')
          setTimeout(() => {
            copyBtn.textContent = '📋 复制'
            copyBtn.classList.remove('copied')
          }, 2000)
        }
        if (navigator.clipboard?.writeText) {
          navigator.clipboard.writeText(codeText).then(copySuccess).catch(() => {
            const ta = document.createElement('textarea')
            ta.value = codeText
            document.body.appendChild(ta)
            ta.select()
            document.execCommand('copy')
            document.body.removeChild(ta)
            copySuccess()
          })
        } else {
          const ta = document.createElement('textarea')
          ta.value = codeText
          document.body.appendChild(ta)
          ta.select()
          document.execCommand('copy')
          document.body.removeChild(ta)
          copySuccess()
        }
      }
    }
  }

  return <div className="markdown" onClick={handleClick} dangerouslySetInnerHTML={{ __html: html }} />
}

export default function App() {
  const [view, setView] = useState<'chat' | 'docs'>('chat')
  const [initial] = useState(loadSessions)
  const [sessions, setSessions] = useState<ChatSession[]>(initial.sessions)
  const [activeId, setActiveId] = useState<string | null>(initial.activeId)
  // 移动端：侧边栏抽屉开关（桌面端无效果）
  const [menuOpen, setMenuOpen] = useState(false)
  // 引用高亮：消息下标 → 当前高亮的引用序号（0-based；无该键表示未高亮）
  const [activeCitation, setActiveCitation] = useState<Record<number, number>>({})
  // 文档分块查看弹层
  const [chunkView, setChunkView] = useState<{ docName: string; chunks: DocChunk[] } | null>(null)
  const [chunkLoading, setChunkLoading] = useState(false)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<string | null>(null)
  const [docSearch, setDocSearch] = useState('')
  const [stats, setStats] = useState({ documents: 0, chunks: 0 })
  const [sysInfo, setSysInfo] = useState<SystemInfo | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  const activeSession = sessions.find((s) => s.id === activeId) ?? null
  const messages = activeSession?.messages ?? []

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
      .catch(() => undefined)
  }, [])

  // 首次进入自动建一个会话（保持旧版开箱即聊的体验）
  useEffect(() => {
    if (sessions.length === 0) {
      const s = newSession()
      setSessions([s])
      setActiveId(s.id)
    }
  }, [sessions.length])

  // 会话持久化：每次变化都保存（带配额保护与 LRU 淘汰）
  useEffect(() => {
    try {
      const saved = saveSessions(sessions, undefined, activeId)
      if (saved.length !== sessions.length) {
        setSessions(saved)
      }
    } catch {
      // 存储不可用时静默降级（隐私模式等）
    }
  }, [sessions, activeId])

  useEffect(() => {
    try {
      if (activeId) localStorage.setItem(ACTIVE_KEY, activeId)
      else localStorage.removeItem(ACTIVE_KEY)
    } catch {
      // 忽略
    }
  }, [activeId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ---------- 会话操作 ----------

  function createSession() {
    const s = newSession()
    setSessions((prev) => [...prev, s])
    setActiveId(s.id)
    setView('chat')
    setMenuOpen(false)
  }

  function switchSession(id: string) {
    setActiveId(id)
    setActiveCitation({})
    setMenuOpen(false)
  }

  function clearActiveSession() {
    if (!activeId || streaming) return
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeId ? { ...s, title: '新会话', messages: [], updatedAt: Date.now() } : s,
      ),
    )
  }

  function deleteSession(id: string) {
    setSessions((prev) => prev.filter((s) => s.id !== id))
    if (id === activeId) {
      const rest = sessions.filter((s) => s.id !== id)
      setActiveId(rest[0]?.id ?? null)
    }
  }

  // ---------- 聊天 ----------

  function handleCopyMessage(index: number, content: string) {
    if (!content) return
    const success = () => {
      setCopiedIndex(index)
      setTimeout(() => {
        setCopiedIndex((prev) => (prev === index ? null : prev))
      }, 2000)
    }
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(content).then(success).catch(() => {
        const ta = document.createElement('textarea')
        ta.value = content
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
        success()
      })
    } else {
      const ta = document.createElement('textarea')
      ta.value = content
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      success()
    }
  }

  function handleStop() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }

  async function runStream(query: string, history: ChatMessage[], targetId: string) {
    setStreaming(true)
    const ac = new AbortController()
    abortControllerRef.current = ac

    let acc = ''
    let citations: Citation[] = []
    const toolCalls: ToolCall[] = []
    let rewrittenNote = ''

    const patch = (content: string, cites: Citation[], tools: ToolCall[], rewritten?: string) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== targetId || s.messages.length === 0) return s
          const copy = [...s.messages]
          copy[copy.length - 1] = {
            role: 'assistant',
            content,
            citations: cites,
            toolCalls: tools,
            rewritten,
          }
          return { ...s, messages: copy, updatedAt: Date.now() }
        }),
      )
    }

    try {
      await streamChat(
        query,
        history,
        {
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
        },
        ac.signal,
      )
    } finally {
      abortControllerRef.current = null
      setStreaming(false)
    }
  }

  async function handleSend() {
    const query = input.trim()
    if (!query || streaming || !activeId) return
    setInput('')

    const targetId = activeId
    const history = activeSession?.messages ?? []
    const userMsg: ChatMessage = { role: 'user', content: query }
    const placeholder: ChatMessage = { role: 'assistant', content: '', citations: [], toolCalls: [] }

    setSessions((prev) =>
      prev.map((s) =>
        s.id === targetId
          ? {
              ...s,
              title: sessionTitle([...s.messages, userMsg]),
              messages: [...s.messages, userMsg, placeholder],
              updatedAt: Date.now(),
            }
          : s,
      ),
    )

    await runStream(query, history, targetId)
  }

  async function handleRegenerate() {
    if (streaming || !activeId || !activeSession) return
    const msgs = activeSession.messages
    if (msgs.length < 2) return
    const lastMsg = msgs[msgs.length - 1]
    const prevMsg = msgs[msgs.length - 2]
    if (lastMsg.role !== 'assistant' || prevMsg.role !== 'user') return

    const query = prevMsg.content
    const history = msgs.slice(0, msgs.length - 2)
    const targetId = activeId

    const placeholder: ChatMessage = { role: 'assistant', content: '', citations: [], toolCalls: [] }
    setSessions((prev) =>
      prev.map((s) =>
        s.id === targetId
          ? {
              ...s,
              messages: [...msgs.slice(0, msgs.length - 1), placeholder],
              updatedAt: Date.now(),
            }
          : s,
      ),
    )

    await runStream(query, history, targetId)
  }

  function toggleCitation(msgIndex: number, citeIndex: number) {
    setActiveCitation((prev) => {
      const next = { ...prev }
      if (next[msgIndex] === citeIndex) delete next[msgIndex]
      else next[msgIndex] = citeIndex
      return next
    })
  }

  function handleRefClick(msgIndex: number, refNum: number) {
    const cites = messages[msgIndex]?.citations
    if (!cites || refNum < 1 || refNum > cites.length) return
    setActiveCitation((prev) => ({ ...prev, [msgIndex]: refNum - 1 }))
  }

  // ---------- 文档操作 ----------

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0 || uploading) return
    setUploading(true)
    const errors: string[] = []
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        setUploadProgress(`正在上传第 ${i + 1}/${files.length} 篇…`)
        try {
          await uploadDoc(file)
        } catch (err) {
          errors.push(`${file.name}: ${err instanceof Error ? err.message : '上传失败'}`)
        }
      }
      await refreshDocs()
      if (errors.length > 0) {
        alert(`部分文档上传失败：\n${errors.join('\n')}`)
      }
    } finally {
      setUploading(false)
      setUploadProgress(null)
      e.target.value = ''
    }
  }

  async function handleDelete(docId: string, docName: string) {
    if (!window.confirm(`确定要删除文档《${docName}》及其向量索引吗？此操作不可恢复。`)) {
      return
    }
    try {
      await deleteDoc(docId)
      await refreshDocs()
    } catch (err) {
      alert(err instanceof Error ? err.message : '删除失败')
    }
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
      {/* 移动端菜单按钮 + 遮罩（桌面端隐藏） */}
      <button
        className="hamburger"
        onClick={() => setMenuOpen((prev) => !prev)}
        aria-label={menuOpen ? '关闭菜单' : '打开菜单'}
      >
        {menuOpen ? '✕' : '☰'}
      </button>
      {menuOpen && <div className="sidebar-overlay" onClick={() => setMenuOpen(false)} />}

      {/* 左侧：导航 + 会话列表 / 系统信息 */}
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <h1 className="logo">📚 DocWise</h1>
        <p className="subtitle">智能知识库问答与 Agent 助手</p>

        <nav className="nav">
          <button
            className={`nav-btn ${view === 'chat' ? 'active' : ''}`}
            onClick={() => {
              setView('chat')
              setMenuOpen(false)
            }}
          >
            💬 对话
          </button>
          <button
            className={`nav-btn ${view === 'docs' ? 'active' : ''}`}
            onClick={() => {
              setView('docs')
              setMenuOpen(false)
            }}
          >
            📄 文档管理
          </button>
        </nav>

        {view === 'chat' && (
          <div className="sessions">
            <div className="sessions-header">
              <span>会话（刷新不丢）</span>
              <div className="sessions-header-actions">
                <button className="new-session" onClick={createSession} title="新建会话">
                  ＋ 新建
                </button>
                <button className="clear-btn" onClick={clearActiveSession} disabled={streaming} title="清空当前会话">
                  🗑 清空
                </button>
              </div>
            </div>
            <ul className="session-list">
              {sessions.length === 0 && <li className="session-empty">还没有会话，点「新建」开始</li>}
              {sessions.map((s) => (
                <li
                  key={s.id}
                  className={`session-item ${s.id === activeId ? 'active' : ''}`}
                  onClick={() => switchSession(s.id)}
                >
                  <span className="session-title">{s.title}</span>
                  <span className="session-time">{timeLabel(s.updatedAt)}</span>
                  <button
                    className="session-delete"
                    title="删除会话"
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteSession(s.id)
                    }}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="sidebar-footer">
          <p>💡 提示：先上传文档，再提问。回答中的 [1] [2] 可点击高亮来源片段。</p>
          {sysInfo && (
            <div className="sys-info">
              <span>🤖 {sysInfo.config.llm_model}</span>
              <span>
                🧠{' '}
                {sysInfo.config.embedding_provider === 'hash'
                  ? '离线哈希嵌入'
                  : sysInfo.config.embedding_model}
              </span>
              <span>✂️ 分词：{sysInfo.config.tokenizer}</span>
              <span>🤖 Agent：{sysInfo.config.agent_enabled ? '开' : '关'}</span>
            </div>
          )}
        </div>
      </aside>

      {view === 'chat' ? (
        /* 右侧：聊天 */
        <main className="chat">
          <div className="chat-body">
            {messages.length === 0 && (
              <div className="welcome">
                <h2>你好，我是 DocWise 👋</h2>
                <p>上传你的文档，然后向我提问。我会基于知识库回答，并标注引用来源。</p>
                <p className="welcome-examples">
                  {sessions.length === 0
                    ? '点击左侧「＋ 新建」开始一个会话'
                    : '试试问：「总结一下知识库里关于 XX 的内容」'}
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={`${msg.role}-${i}`} className={`msg msg-${msg.role}`}>
                <div className="msg-bubble">
                  {msg.role === 'assistant' ? (
                    msg.content ? (
                      <Markdown text={msg.content} onRefClick={(n) => handleRefClick(i, n)} />
                    ) : streaming && i === messages.length - 1 ? (
                      '…'
                    ) : (
                      ''
                    )
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
                    {msg.citations.map((c, ci) => (
                      <button
                        key={c.chunk_id}
                        className={`citation ${activeCitation[i] === ci ? 'active' : ''}`}
                        title="点击高亮对应来源片段"
                        onClick={() => toggleCitation(i, ci)}
                      >
                        📖 {c.doc_name} · 片段{c.index} · 相似度 {c.score.toFixed(2)}
                      </button>
                    ))}
                  </div>
                )}
                {msg.role === 'assistant' && activeCitation[i] !== undefined && (
                  <div className="citation-detail highlighted">
                    {msg.citations?.[activeCitation[i]]?.text ?? ''}
                  </div>
                )}
                {msg.role === 'assistant' && msg.content && (!streaming || i !== messages.length - 1) && (
                  <div className="msg-actions">
                    <button
                      type="button"
                      className="msg-action-btn"
                      onClick={() => handleCopyMessage(i, msg.content)}
                      title="复制回答全文"
                    >
                      {copiedIndex === i ? '✅ 已复制' : '📋 复制全文'}
                    </button>
                    {i === messages.length - 1 && !streaming && (
                      <button
                        type="button"
                        className="msg-action-btn"
                        onClick={handleRegenerate}
                        title="重新生成此回答"
                      >
                        🔄 重新生成
                      </button>
                    )}
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
              placeholder={
                !activeId
                  ? '先点击左侧「＋ 新建」开始会话'
                  : streaming
                    ? '正在生成…'
                    : '输入问题，Enter 发送，Shift+Enter 换行'
              }
              rows={2}
              disabled={streaming}
            />
            {streaming ? (
              <button className="send-btn stop-btn" onClick={handleStop} title="停止生成">
                ⏹ 停止
              </button>
            ) : (
              <button className="send-btn" onClick={handleSend} disabled={!input.trim() || !activeId}>
                发送
              </button>
            )}
          </div>
        </main>
      ) : (
        /* 文档管理视图 */
        <main className="docs-page">
          <div className="docs-header">
            <h2>📚 文档管理</h2>
            <div className="docs-header-actions">
              <input
                type="text"
                className="docs-search-input"
                placeholder="🔍 搜索文档名称…"
                value={docSearch}
                onChange={(e) => setDocSearch(e.target.value)}
              />
              <label className={`upload-btn ${uploading ? 'disabled' : ''}`}>
                {uploadProgress ?? (uploading ? '⏳ 上传中…' : '📤 上传文档（txt / md / pdf / docx）')}
                <input
                  type="file"
                  accept=".txt,.md,.markdown,.pdf,.docx"
                  hidden
                  multiple
                  disabled={uploading}
                  onChange={handleUpload}
                />
              </label>
            </div>
          </div>
          <div className="stats">
            <span>📄 文档 {stats.documents}</span>
            <span>🧩 分块 {stats.chunks}</span>
          </div>
          <div className="docs-table">
            <div className="docs-row docs-head">
              <span>文档标题</span>
              <span>上传时间</span>
              <span>分块数</span>
              <span>操作</span>
            </div>
            {docs.length === 0 && <p className="docs-empty">还没有文档，先上传几份试试</p>}
            {docs.length > 0 &&
              docs.filter((d) => !docSearch.trim() || d.name.toLowerCase().includes(docSearch.trim().toLowerCase())).length === 0 && (
                <p className="docs-empty">未找到匹配「{docSearch}」的文档</p>
              )}
            {docs
              .filter((d) => !docSearch.trim() || d.name.toLowerCase().includes(docSearch.trim().toLowerCase()))
              .map((doc) => (
                <div key={doc.doc_id} className="docs-row">
                  <span className="doc-name" title={doc.name}>
                    {doc.name}
                  </span>
                  <span className="doc-meta">{doc.created_at ?? '—'}</span>
                  <span className="doc-meta">{doc.chunk_count} 块</span>
                  <span className="doc-actions">
                    <button className="doc-view" onClick={() => handleViewChunks(doc)} title="查看分块">
                      🧩 查看分块
                    </button>
                    <button className="doc-delete" onClick={() => handleDelete(doc.doc_id, doc.name)} title="删除">
                      🗑 删除
                    </button>
                  </span>
                </div>
              ))}
          </div>
        </main>
      )}

      {/* 文档分块查看弹层 */}
      {chunkView && (
        <div className="modal-overlay" onClick={() => setChunkView(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span>🧩 《{chunkView.docName}》的分块（{chunkView.chunks.length} 块）</span>
              <button className="modal-close" onClick={() => setChunkView(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              {chunkLoading && <p className="modal-hint">加载中…</p>}
              {!chunkLoading && chunkView.chunks.length === 0 && (
                <p className="modal-hint">暂无分块（文档可能太短或为空）</p>
              )}
              {chunkView.chunks.map((c) => (
                <div key={c.chunk_id} className="chunk-item">
                  <div className="chunk-header">
                    <span className="chunk-index">#{c.index}</span>
                    {c.heading_path && (
                      <span className="chunk-heading" title={c.heading_path}>
                        🏷️ {c.heading_path}
                      </span>
                    )}
                  </div>
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
