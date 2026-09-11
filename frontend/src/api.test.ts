import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamChat } from './api'

function sseResponse(events: string[]): Response {
  const body = events.map((e) => `data: ${e}\n\n`).join('')
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(body))
      controller.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamChat', () => {
  it('解析 SSE 事件：citations / delta / tool_result / done', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse([
          JSON.stringify({
            type: 'citations',
            citations: [
              { chunk_id: 'c1', doc_id: 'd1', doc_name: 'a.md', index: 0, score: 0.9, text: '片段' },
            ],
          }),
          JSON.stringify({ type: 'delta', content: '你好' }),
          JSON.stringify({ type: 'tool_result', name: 'calc', result: '42' }),
          JSON.stringify({ type: 'done' }),
        ]),
      ),
    )

    const deltas: string[] = []
    const tools: string[] = []
    let citations: unknown = null
    let doneCount = 0

    await streamChat('问题', [], {
      onCitations: (c) => {
        citations = c
      },
      onDelta: (d) => deltas.push(d),
      onToolResult: (name) => tools.push(name),
      onDone: () => {
        doneCount += 1
      },
    })

    expect(citations).toHaveLength(1)
    expect((citations as Array<Record<string, unknown>>)[0]).toMatchObject({
      doc_name: 'a.md',
      score: 0.9,
    })
    expect(deltas).toEqual(['你好'])
    expect(tools).toEqual(['calc'])
    // {"type":"done"} 事件 + 流结束兜底各触发一次
    expect(doneCount).toBe(2)
  })

  it('HTTP 非 200 时走 onError 回调', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('oops', { status: 500 })))
    const errors: string[] = []
    await streamChat('问题', [], { onError: (m) => errors.push(m) })
    expect(errors).toEqual(['请求失败：HTTP 500'])
  })

  it('HTTP 错误时优先提取响应体的 detail 说明', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: '请求过于频繁，请稍后再试' }), {
            status: 429,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )
    const errors: string[] = []
    await streamChat('问题', [], { onError: (m) => errors.push(m) })
    expect(errors).toEqual(['请求过于频繁，请稍后再试'])
  })

  it('被 AbortController 中断 fetch 时优雅触发 onDone 且不报错', async () => {
    const ac = new AbortController()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        ac.abort()
        const err = new Error('The user aborted a request.')
        err.name = 'AbortError'
        throw err
      }),
    )

    const errors: string[] = []
    let doneCalled = false
    await streamChat(
      '问题',
      [],
      {
        onError: (m) => errors.push(m),
        onDone: () => {
          doneCalled = true
        },
      },
      ac.signal,
    )

    expect(errors).toEqual([])
    expect(doneCalled).toBe(true)
  })

  it('读取流过程中被中断时优雅触发 onDone 且不报错', async () => {
    const ac = new AbortController()
    let sent = false
    const mockStream = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (!sent) {
          controller.enqueue(new TextEncoder().encode('data: {"type": "delta", "content": "部分内容"}\n\n'))
          sent = true
        } else {
          ac.abort()
          const err = new Error('The user aborted a request.')
          err.name = 'AbortError'
          controller.error(err)
        }
      },
    })

    vi.stubGlobal('fetch', vi.fn(async () => new Response(mockStream, { status: 200 })))

    const deltas: string[] = []
    const errors: string[] = []
    let doneCalled = false

    await streamChat(
      '问题',
      [],
      {
        onDelta: (d) => deltas.push(d),
        onError: (m) => errors.push(m),
        onDone: () => {
          doneCalled = true
        },
      },
      ac.signal,
    )

    expect(deltas).toEqual(['部分内容'])
    expect(errors).toEqual([])
    expect(doneCalled).toBe(true)
  })
})

