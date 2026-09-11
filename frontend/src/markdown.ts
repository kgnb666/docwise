import { marked } from 'marked'
import Prism from 'prismjs'
import 'prismjs/components/prism-python'
import 'prismjs/components/prism-bash'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-typescript'
import 'prismjs/components/prism-javascript'
import 'prismjs/components/prism-sql'
import 'prismjs/components/prism-yaml'
import 'prismjs/components/prism-markdown'

const LANG_ALIASES: Record<string, string> = {
  py: 'python',
  js: 'javascript',
  ts: 'typescript',
  sh: 'bash',
  shell: 'bash',
  yml: 'yaml',
  md: 'markdown',
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function highlightCode(code: string, rawLang?: string): string {
  const lang = (rawLang || '').trim().toLowerCase()
  const targetLang = LANG_ALIASES[lang] || lang
  if (targetLang && Prism.languages[targetLang]) {
    try {
      return Prism.highlight(code, Prism.languages[targetLang], targetLang)
    } catch {
      // 降级使用普通转义
    }
  }
  return escapeHtml(code)
}

const renderer = new marked.Renderer()
renderer.code = function (code: string, infostring: string | undefined): string {
  const rawLang = (infostring || '').trim().split(/\s+/)[0]
  const displayLang = rawLang || 'text'
  const highlighted = highlightCode(code, rawLang)
  return `<div class="code-block-wrapper"><div class="code-block-header"><span class="code-block-lang">${escapeHtml(displayLang)}</span><button type="button" class="code-copy-btn" title="复制代码">📋 复制</button></div><pre><code class="language-${escapeHtml(displayLang)}">${highlighted}</code></pre></div>`
}

marked.setOptions({
  renderer,
  gfm: true,
  breaks: true,
})

export { marked }

/** 把消毒后的 HTML 中的 [1]/[2] 引用序号替换为可点击按钮，同时保护代码块（pre/code）与 HTML 标签属性不被破坏。 */
export function linkifyCitationRefs(html: string): string {
  const parts = html.split(/(<pre[\s\S]*?<\/pre>|<code[\s\S]*?<\/code>|<[^>]+>)/gi)
  return parts
    .map((part) => {
      if (part.startsWith('<')) {
        return part
      }
      return part.replace(
        /\[(\d{1,2})\]/g,
        (_match, n: string) =>
          `<button type="button" class="ref-chip" data-ref="${n}">[${n}]</button>`,
      )
    })
    .join('')
}

