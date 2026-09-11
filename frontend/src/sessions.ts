// 会话模型与 localStorage 持久化：多会话 + 当前会话，刷新不丢
import type { ChatMessage } from './types'

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  updatedAt: number
}

export const MAX_SESSIONS = 30
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

/**
 * 按活跃时间（updatedAt 降序）修剪会话，超出上限时淘汰最久未活跃的空闲会话。
 * 若指定了 activeId，确保当前激活的会话不会被淘汰。
 */
export function pruneSessions(
  sessions: ChatSession[],
  max: number = MAX_SESSIONS,
  activeId?: string | null,
): ChatSession[] {
  if (sessions.length <= max) return sessions

  // 按 updatedAt 降序排序（较新的在前）
  const sorted = [...sessions].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))

  let retained: ChatSession[] = []
  if (activeId && sessions.some((s) => s.id === activeId)) {
    const active = sessions.find((s) => s.id === activeId)!
    const others = sorted.filter((s) => s.id !== activeId)
    retained = [active, ...others.slice(0, Math.max(0, max - 1))]
  } else {
    retained = sorted.slice(0, max)
  }

  const retainedIds = new Set(retained.map((s) => s.id))
  // 保持在原有列表中的相对顺序
  return sessions.filter((s) => retainedIds.has(s.id))
}

/**
 * 安全保存会话列表到 localStorage：
 * 1. 预先修剪至最多 MAX_SESSIONS 个会话；
 * 2. 若发生 QuotaExceededError 或写入异常，循环淘汰最旧会话并重试写入；
 * 3. 返回最终成功写入（或最后修剪）的会话列表。
 */
export function saveSessions(
  sessions: ChatSession[],
  storage?: Pick<Storage, 'setItem' | 'getItem'> | null,
  activeId?: string | null,
): ChatSession[] {
  const store = storage ?? (typeof window !== 'undefined' ? window.localStorage : null)
  let current = pruneSessions(sessions, MAX_SESSIONS, activeId)
  if (!store) return current

  while (current.length > 0) {
    try {
      store.setItem(SESSIONS_KEY, JSON.stringify(current))
      return current
    } catch {
      // 达到浏览器存储上限或写入异常：进一步淘汰最旧会话重试
      if (current.length <= 1) {
        break
      }
      current = pruneSessions(current, current.length - 1, activeId)
    }
  }
  return current
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
        const pruned = pruneSessions(sessions, MAX_SESSIONS)
        const activeId = store.getItem(ACTIVE_KEY)
        return {
          sessions: pruned,
          activeId: pruned.some((s) => s.id === activeId) ? activeId : (pruned[0]?.id ?? null),
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
