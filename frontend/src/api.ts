// 与后端交互的 API 封装（走 Vite 代理，浏览器侧无需关心跨域）

import type { ChatMessage, Citation, DocInfo, Stats } from './types'

export interface StreamHandlers {
  onCitations?: (citations: Citation[]) => void
  onDelta?: (content: string) => void
  onToolResult?: (name: string, result: string) => void
  onQueryRewritten?: (original: string, rewritten: string) => void
  onDone?: () => void
  onError?: (message: string) => void
}

/** 流式问答：解析后端 SSE 事件（citations / delta / done / error） */
export async function streamChat(
  query: string,
  history: ChatMessage[],
  handlers: StreamHandlers,
): Promise<void> {
  let resp: Response
  try {
    resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        history: history.map((m) => ({ role: m.role, content: m.content })),
      }),
    })
  } catch {
    handlers.onError?.('无法连接后端服务，请确认后端已启动（uvicorn）')
    return
  }

  if (!resp.ok || !resp.body) {
    handlers.onError?.(`请求失败：HTTP ${resp.status}`)
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const handleEvent = (data: string) => {
    if (data === '[DONE]') {
      handlers.onDone?.()
      return
    }
    try {
      const evt = JSON.parse(data)
      switch (evt.type) {
        case 'citations':
          handlers.onCitations?.(evt.citations)
          break
        case 'delta':
          handlers.onDelta?.(evt.content)
          break
        case 'tool_result':
          handlers.onToolResult?.(evt.name, evt.result)
          break
        case 'query_rewritten':
          handlers.onQueryRewritten?.(evt.original, evt.rewritten)
          break
        case 'error':
          handlers.onError?.(evt.message)
          break
        case 'done':
          handlers.onDone?.()
          break
      }
    } catch {
      // 忽略无法解析的行
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 消息以空行分隔，逐条处理
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      handleEvent(line.slice(5).trim())
    }
  }
  handlers.onDone?.()
}

export async function fetchDocs(): Promise<DocInfo[]> {
  const resp = await fetch('/api/documents')
  const data = await resp.json()
  return data.documents ?? []
}

export async function fetchStats(): Promise<Stats> {
  const resp = await fetch('/api/documents/stats')
  return resp.json()
}

export interface SystemInfo {
  stats: { documents: number; chunks: number }
  config: {
    llm_model: string
    embedding_provider: string
    embedding_model: string
    tokenizer: string
    agent_enabled: boolean
  }
}

/** 系统状态概览（模型 / 分词 / 统计）。 */
export async function fetchSystemInfo(): Promise<SystemInfo> {
  const resp = await fetch('/api/health')
  return resp.json()
}

export async function uploadDoc(file: File): Promise<DocInfo> {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch('/api/documents', { method: 'POST', body: form })
  if (!resp.ok) {
    const err = await resp.json().catch(() => null)
    throw new Error(err?.detail ?? `上传失败：HTTP ${resp.status}`)
  }
  return resp.json()
}

export async function deleteDoc(docId: string): Promise<void> {
  await fetch(`/api/documents/${docId}`, { method: 'DELETE' })
}

export interface DocChunk {
  chunk_id: string
  index: number
  text: string
}

/** 查看某文档被切成哪些块（演示"知识如何被切分"）。 */
export async function fetchDocChunks(docId: string): Promise<DocChunk[]> {
  const resp = await fetch(`/api/documents/${docId}/chunks`)
  if (!resp.ok) return []
  const data = await resp.json()
  return data.chunks ?? []
}
