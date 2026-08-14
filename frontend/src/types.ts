// 与后端接口对应的类型定义

export interface Citation {
  chunk_id: string
  doc_id: string
  doc_name: string
  index: number
  score: number
  text: string
}

export interface ToolCall {
  name: string
  result: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  toolCalls?: ToolCall[]
  /** 追问被系统改写后的检索查询（用于展示） */
  rewritten?: string
}

export interface DocInfo {
  doc_id: string
  name: string
  chunk_count: number
  created_at?: string
}

export interface Stats {
  documents: number
  chunks: number
}
