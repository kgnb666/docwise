import { describe, expect, it } from 'vitest'
import { accountSessionStorage, loadSessions, pruneSessions, saveSessions, sessionTitle } from './sessions'
import type { ChatMessage } from './types'

function storage(data: Record<string, string>): Pick<Storage, 'getItem'> {
  return {
    getItem: (key: string) => data[key] ?? null,
  }
}

it('不同账号的本地会话隔离，旧会话不会进入任何账号', () => {
  const data = new Map([['docwise.messages.v1', '[{"role":"user","content":"旧会话"}]']])
  const shared = {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value) },
    removeItem: (key: string) => { data.delete(key) },
  }
  const alice = accountSessionStorage('alice-id', shared)
  const bob = accountSessionStorage('bob-id', shared)
  saveSessions([{ id: 's1', title: '私有会话', messages: [], updatedAt: 1 }], alice)

  expect(loadSessions(alice).activeId).toBe('s1')
  expect(loadSessions(bob)).toEqual({ sessions: [], activeId: null })
  expect(shared.getItem('docwise.messages.v1')).toContain('旧会话')
})

describe('sessionTitle', () => {
  it('取第一条用户消息作为标题，超 18 字截断', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: '这是一个非常长的用户问题用来验证标题截断逻辑是否生效' },
    ]
    const title = sessionTitle(messages)
    expect(title).toHaveLength(19) // 18 字符 + 省略号
    expect(title.endsWith('…')).toBe(true)
  })

  it('没有用户消息时返回"新会话"', () => {
    expect(sessionTitle([])).toBe('新会话')
    expect(sessionTitle([{ role: 'assistant', content: '回答' }])).toBe('新会话')
  })
})

describe('loadSessions', () => {
  it('从 localStorage 恢复多会话并优先选中当前会话', () => {
    const store = storage({
      'docwise.sessions.v1': JSON.stringify([
        { id: 's1', title: '会话一', messages: [{ role: 'user', content: '问题1' }], updatedAt: 1 },
        { id: 's2', title: '会话二', messages: [], updatedAt: 2 },
      ]),
      'docwise.activeSession.v1': 's2',
    })
    const { sessions, activeId } = loadSessions(store)
    expect(sessions).toHaveLength(2)
    expect(activeId).toBe('s2')
  })

  it('当前会话失效时回退到第一个会话；损坏数据返回空', () => {
    const store = storage({
      'docwise.sessions.v1': JSON.stringify([{ id: 's1', title: '会话一', messages: [], updatedAt: 1 }]),
      'docwise.activeSession.v1': 'missing',
    })
    expect(loadSessions(store).activeId).toBe('s1')
    expect(loadSessions(storage({ 'docwise.sessions.v1': '{broken' }))).toEqual({
      sessions: [],
      activeId: null,
    })
    expect(loadSessions(storage({}))).toEqual({ sessions: [], activeId: null })
  })
})

describe('pruneSessions', () => {
  it('未超过上限时原样返回', () => {
    const list = [
      { id: '1', title: 'A', messages: [], updatedAt: 10 },
      { id: '2', title: 'B', messages: [], updatedAt: 20 },
    ]
    expect(pruneSessions(list, 5)).toEqual(list)
  })

  it('超过上限时按 updatedAt 淘汰最久未活跃的会话', () => {
    const list = Array.from({ length: 35 }, (_, i) => ({
      id: `s${i}`,
      title: `会话${i}`,
      messages: [],
      updatedAt: i * 100,
    }))
    const pruned = pruneSessions(list, 30)
    expect(pruned).toHaveLength(30)
    // 最旧的 5 个（updatedAt 0 到 400）应被淘汰
    expect(pruned.some((s) => s.id === 's0')).toBe(false)
    expect(pruned.some((s) => s.id === 's4')).toBe(false)
    expect(pruned.some((s) => s.id === 's5')).toBe(true)
    expect(pruned.some((s) => s.id === 's34')).toBe(true)
  })

  it('始终保留当前激活的会话（activeId）', () => {
    const list = [
      { id: 'old_active', title: '激活老会话', messages: [], updatedAt: 1 },
      { id: 's2', title: '会话2', messages: [], updatedAt: 20 },
      { id: 's3', title: '会话3', messages: [], updatedAt: 30 },
    ]
    // 限制最多 2 个，通常会保留 s2 和 s3，但指定 old_active 后必须保留 old_active
    const pruned = pruneSessions(list, 2, 'old_active')
    expect(pruned).toHaveLength(2)
    expect(pruned.some((s) => s.id === 'old_active')).toBe(true)
    expect(pruned.some((s) => s.id === 's3')).toBe(true)
    expect(pruned.some((s) => s.id === 's2')).toBe(false)
  })
})

describe('saveSessions', () => {
  it('保存时自动修剪超出 MAX_SESSIONS 的会话', () => {
    const mockStorage: Record<string, string> = {}
    const store = {
      getItem: (k: string) => mockStorage[k] ?? null,
      setItem: (k: string, v: string) => {
        mockStorage[k] = v
      },
    }
    const list = Array.from({ length: 35 }, (_, i) => ({
      id: `s${i}`,
      title: `会话${i}`,
      messages: [],
      updatedAt: i * 10,
    }))
    const saved = saveSessions(list, store)
    expect(saved).toHaveLength(30)
    expect(JSON.parse(mockStorage['docwise.sessions.v1'])).toHaveLength(30)
  })

  it('遇存储配额异常（QuotaExceededError）时自动淘汰最旧会话并重试成功', () => {
    let callCount = 0
    const mockStorage: Record<string, string> = {}
    const store = {
      getItem: (k: string) => mockStorage[k] ?? null,
      setItem: (k: string, v: string) => {
        callCount++
        // 第一次和第二次写入都模拟容量超限异常
        if (callCount <= 2) {
          throw new DOMException('Quota exceeded', 'QuotaExceededError')
        }
        mockStorage[k] = v
      },
    }
    const list = [
      { id: 's1', title: '会话1', messages: [], updatedAt: 10 },
      { id: 's2', title: '会话2', messages: [], updatedAt: 20 },
      { id: 's3', title: '会话3', messages: [], updatedAt: 30 },
    ]
    const saved = saveSessions(list, store, 's3')
    expect(callCount).toBe(3)
    // 经历了 2 次淘汰重试，最终保存了 1 个会话（s3）
    expect(saved).toHaveLength(1)
    expect(saved[0].id).toBe('s3')
    expect(JSON.parse(mockStorage['docwise.sessions.v1'])).toHaveLength(1)
  })
})
