import { describe, expect, it } from 'vitest'
import { linkifyCitationRefs } from './markdown'

describe('linkifyCitationRefs', () => {
  it('把 [1] / [12] 引用序号替换为可点击按钮', () => {
    const html = linkifyCitationRefs('<p>见 [1] 与 [12] 两处来源</p>')
    expect(html).toContain('<button type="button" class="ref-chip" data-ref="1">[1]</button>')
    expect(html).toContain('<button type="button" class="ref-chip" data-ref="12">[12]</button>')
  })

  it('非数字方括号与普通文本保持不变', () => {
    const html = linkifyCitationRefs('<p>[x] 是变量，[1.5] 是数字</p>')
    expect(html).toContain('[x] 是变量')
    expect(html).toContain('[1.5] 是数字')
    expect(html).not.toContain('ref-chip')
  })
})

describe('highlightCode and marked code blocks', () => {
  it('正确渲染代码块包装器、语言标识与复制按钮', async () => {
    const { marked } = await import('./markdown')
    const md = '```python\ndef hello():\n    return "world"\n```'
    const html = marked.parse(md) as string

    expect(html).toContain('class="code-block-wrapper"')
    expect(html).toContain('class="code-block-header"')
    expect(html).toContain('<span class="code-block-lang">python</span>')
    expect(html).toContain('<button type="button" class="code-copy-btn" title="复制代码">📋 复制</button>')
    expect(html).toContain('<pre><code class="language-python">')
    expect(html).toContain('token keyword')
  })

  it('未指定语言时默认回退至 text 并安全转义 HTML 特殊字符', async () => {
    const { marked } = await import('./markdown')
    const md = '```\n<script>alert(1)</script>\n```'
    const html = marked.parse(md) as string

    expect(html).toContain('<span class="code-block-lang">text</span>')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).not.toContain('<script>')
  })
})

