// 与后端交互的 API 封装（走 Vite 代理，浏览器侧无需关心跨域）

import type { ChatMessage, Citation, DocInfo, Stats } from './types'

export interface Account {
  id: string
  username: string
}

export const SESSION_ENDED = 'docwise:session-ended'

async function workspaceFetch(accountId: string, url: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers)
  headers.set('X-DocWise-Account', accountId)
  const response = await fetch(url, { ...init, headers, cache: 'no-store' })
  if (response.status === 401 && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(SESSION_ENDED, { detail: accountId }))
  }
  return response
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const data = await response.json().catch(() => null)
  return new Error(typeof data?.detail === 'string' ? data.detail : fallback)
}

export async function fetchAccount(signal?: AbortSignal): Promise<Account | null> {
  const response = await fetch('/api/auth/me', { cache: 'no-store', signal })
  if (response.status === 401) return null
  if (!response.ok) throw await responseError(response, '无法读取登录状态，请重试')
  return response.json()
}

export async function loginAccount(username: string, password: string): Promise<Account> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    cache: 'no-store',
  })
  if (!response.ok) throw await responseError(response, '登录失败，请检查账号和密码')
  return response.json()
}

export async function logoutAccount(accountId: string): Promise<boolean> {
  const response = await workspaceFetch(accountId, '/api/auth/logout', { method: 'POST' })
  if (!response.ok && response.status !== 401) {
    throw await responseError(response, '退出失败，请重试')
  }
  return response.ok
}

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
  accountId: string,
  query: string,
  history: ChatMessage[],
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let resp: Response
  try {
    resp = await workspaceFetch(accountId, '/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        history: history.map((m) => ({ role: m.role, content: m.content })),
      }),
      signal,
    })
  } catch (err) {
    if ((err as Error)?.name === 'AbortError' || signal?.aborted) {
      handlers.onDone?.()
      return
    }
    handlers.onError?.('无法连接后端服务，请确认后端已启动（uvicorn）')
    return
  }

  if (!resp.ok || !resp.body) {
    const errData = await resp.json().catch(() => null)
    const msg = (errData && typeof errData.detail === 'string') ? errData.detail : `请求失败：HTTP ${resp.status}`
    handlers.onError?.(msg)
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

  try {
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
  } catch (err) {
    if ((err as Error)?.name === 'AbortError' || signal?.aborted) {
      handlers.onDone?.()
      return
    }
    handlers.onError?.('流式读取中断或网络异常')
  }
}

export async function fetchDocs(accountId: string): Promise<DocInfo[]> {
  const resp = await workspaceFetch(accountId, '/api/documents')
  if (!resp.ok) throw await responseError(resp, '无法读取文档')
  const data = await resp.json()
  return data.documents ?? []
}

export async function fetchStats(accountId: string): Promise<Stats> {
  const resp = await workspaceFetch(accountId, '/api/documents/stats')
  if (!resp.ok) throw await responseError(resp, '无法读取文档统计')
  return resp.json()
}

export interface SystemInfo {
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

export async function uploadDoc(accountId: string, file: File, signal?: AbortSignal): Promise<DocInfo> {
  const form = new FormData()
  form.append('file', file)
  const resp = await workspaceFetch(accountId, '/api/documents', { method: 'POST', body: form, signal })
  if (!resp.ok) throw await responseError(resp, `上传失败：HTTP ${resp.status}`)
  return resp.json()
}

export async function deleteDoc(accountId: string, docId: string): Promise<void> {
  const resp = await workspaceFetch(accountId, `/api/documents/${docId}`, { method: 'DELETE' })
  if (!resp.ok) throw await responseError(resp, `删除失败：HTTP ${resp.status}`)
}

export interface DocChunk {
  chunk_id: string
  index: number
  text: string
  heading_path?: string
}

/** 查看某文档被切成哪些块（演示"知识如何被切分"）。 */
export async function fetchDocChunks(accountId: string, docId: string): Promise<DocChunk[]> {
  const resp = await workspaceFetch(accountId, `/api/documents/${docId}/chunks`)
  if (!resp.ok) return []
  const data = await resp.json()
  return data.chunks ?? []
}
