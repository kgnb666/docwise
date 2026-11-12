import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { fetchAccount, loginAccount, logoutAccount, SESSION_ENDED, type Account } from './api'
import { makeId } from './sessions'

const SESSION_CHANGED_KEY = 'docwise.auth.changed'

function notifyOtherTabs() {
  try {
    window.localStorage.setItem(SESSION_CHANGED_KEY, makeId())
  } catch {
    // 存储不可用时，标签页重新获得焦点时校验会话。
  }
}

export function AuthGate({ children }: {
  children: (account: Account, logout: () => Promise<void>) => ReactNode
}) {
  const [account, setAccount] = useState<Account | null | undefined>(undefined)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    function sessionChanged(event: StorageEvent) {
      if (event.key === SESSION_CHANGED_KEY) {
        controller.abort()
        setAccount(null)
      }
    }
    window.addEventListener('storage', sessionChanged)
    fetchAccount(controller.signal).then(
      (current) => { if (!controller.signal.aborted) setAccount(current) },
      () => {
        if (!controller.signal.aborted) {
          setAccount(null)
          setError('无法读取登录状态，请重试')
        }
      },
    )
    return () => {
      controller.abort()
      window.removeEventListener('storage', sessionChanged)
    }
  }, [])

  useEffect(() => {
    if (!account) return
    const accountId = account.id
    const controller = new AbortController()
    function verifySession() {
      fetchAccount(controller.signal).then((current) => {
        if (!controller.signal.aborted && current?.id !== accountId) {
          setAccount((active) => active?.id === accountId ? null : active)
        }
      }).catch(() => undefined)
    }
    window.addEventListener('focus', verifySession)
    window.addEventListener('pageshow', verifySession)
    return () => {
      controller.abort()
      window.removeEventListener('focus', verifySession)
      window.removeEventListener('pageshow', verifySession)
    }
  }, [account])

  useEffect(() => {
    function sessionEnded(event: Event) {
      const accountId = (event as CustomEvent<string>).detail
      setAccount((current) => current?.id === accountId ? null : current)
    }
    window.addEventListener(SESSION_ENDED, sessionEnded)
    return () => window.removeEventListener(SESSION_ENDED, sessionEnded)
  }, [])

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    const form = event.currentTarget
    const data = new FormData(form)
    setSubmitting(true)
    setError('')
    try {
      const current = await loginAccount(String(data.get('username')), String(data.get('password')))
      form.reset()
      setAccount(current)
      notifyOtherTabs()
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  if (account) {
    return children(account, async () => {
      if (await logoutAccount(account.id)) notifyOtherTabs()
      setAccount(null)
    })
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="auth-title">
        <h1 id="auth-title">DocWise</h1>
        {account === undefined ? (
          <p role="status">正在检查登录状态…</p>
        ) : (
          <form className="auth-form" onSubmit={login} aria-busy={submitting}>
            <p>登录后打开你的知识库</p>
            <label>
              账号
              <input name="username" autoComplete="username" required maxLength={64} />
            </label>
            <label>
              密码
              <input name="password" type="password" autoComplete="current-password" required maxLength={128} />
            </label>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button type="submit" className="upload-btn" disabled={submitting}>
              {submitting ? '正在登录…' : '登录'}
            </button>
          </form>
        )}
      </section>
    </main>
  )
}
