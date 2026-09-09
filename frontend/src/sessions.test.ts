import { describe, expect, it } from 'vitest'
import { loadSessions, sessionTitle } from './sessions'
import type { ChatMessage } from './types'

function storage(data: Record<string, string>): Pick<Storage, 'getItem'> {
  return {
    getItem: (key: string) => data[key] ?? null,
  }
}

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
