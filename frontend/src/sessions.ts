// 会话模型与 localStorage 持久化：多会话 + 当前会话，刷新不丢
import type { ChatMessage } from './types'

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  updatedAt: number
}

export const SESSIONS_KEY = 'docwise.sessions.v1'
export const ACTIVE_KEY = 'docwise.activeSession.v1'
const LEGACY_KEY = 'docwise.messages.v1'

export function makeId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function sessionTitle(messages: ChatMessage[]): string {
  const first = messages.find((m) => m.role === 'user')
  if (!first) return '新会话'
  const text = first.content.trim().replace(/\s+/g, ' ')
  return text.length > 18 ? `${text.slice(0, 18)}…` : text
}

export function newSession(messages: ChatMessage[] = []): ChatSession {
  return { id: makeId(), title: sessionTitle(messages), messages, updatedAt: Date.now() }
}

export function loadSessions(
  storage?: Pick<Storage, 'getItem'> | null,
): { sessions: ChatSession[]; activeId: string | null } {
  const store = storage ?? (typeof window !== 'undefined' ? window.localStorage : null)
  if (!store) return { sessions: [], activeId: null }
  try {
    const raw = store.getItem(SESSIONS_KEY)
    if (raw) {
      const parsed: unknown = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        const sessions = parsed.filter(
          (s): s is ChatSession => !!s && typeof s.id === 'string' && Array.isArray(s.messages),
        )
        const activeId = store.getItem(ACTIVE_KEY)
        return {
          sessions,
          activeId: sessions.some((s) => s.id === activeId) ? activeId : (sessions[0]?.id ?? null),
        }
      }
    }
  } catch {
    // localStorage 损坏/不可用时降级为空会话
  }
  try {
    // 兼容旧版单会话存储：迁移成第一个会话
    const raw = store.getItem(LEGACY_KEY)
    if (raw) {
      const parsed: unknown = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        const s = newSession(parsed)
        return { sessions: [s], activeId: s.id }
      }
    }
  } catch {
    // 忽略迁移失败
  }
  return { sessions: [], activeId: null }
}

export function timeLabel(ts: number): string {
  const d = new Date(ts)
  const now = new Date()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return d.toDateString() === now.toDateString() ? `${hh}:${mm}` : `${d.getMonth() + 1}/${d.getDate()}`
}
