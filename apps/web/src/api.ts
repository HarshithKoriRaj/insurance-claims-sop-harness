// Typed client for the Claims Assistant backend.
//
// All requests use relative "/api/..." URLs so the same code works in dev
// (proxied by Vite to http://127.0.0.1:8000, see vite.config.ts) and in
// production (served by the Python backend at "/").

export type Phase =
  | 'VERIFY_ID'
  | 'RESOLVE_INTENT'
  | 'PROCESS_CASE'
  | 'POST_PROCESS'

export type IdentityField = 'full_name' | 'dob' | 'phone' | 'email' | 'ssn_last4'

export type Lifecycle = 'ACTIVE' | 'HANDOFF_PENDING' | 'CLOSED'

export type ModelMode = 'claude' | 'openai' | 'offline'

export type SummaryStatus = 'none' | 'offered' | 'sent' | 'skipped'

export type ActionType =
  | 'send_summary'
  | 'skip_summary'
  | 'request_human'
  | 'end_conversation'

export interface Message {
  id: number
  role: 'user' | 'assistant'
  text: string
  phase: Phase
  at: string
}

export interface CaseHints {
  case_id: string | null
  case_type: string | null
  status: string | null
  month: number | null
  year: number | null
}

export interface SessionView {
  session_id: string
  phase: Phase
  lifecycle: Lifecycle
  messages: Message[]
  verification: {
    verified: boolean
    fields_provided: IdentityField[]
    fields_required: number
    failed_attempts: number
    max_attempts: number
  }
  selected_case: null | { case_id: string; case_type: string; status: string }
  memory: {
    intent: string | null
    followup_topic: string | null
    case_hints: CaseHints
  }
  recovery: { off_topic: number; refusals: number }
  summary: {
    status: SummaryStatus
    subject: string | null
    body: string | null
    recipient: string | null
    delivered: boolean
  }
  available_actions: ActionType[]
  business_date: string
  model_mode: ModelMode
}

export interface CreateSessionResponse {
  session_id: string
  token: string
  view: SessionView
}

export interface SessionViewResponse {
  view: SessionView
}

export interface HealthResponse {
  status: string
  model: string
  model_mode: ModelMode
}

export interface StoredSession {
  session_id: string
  token: string
}

/** Error raised for any non-2xx response. `status` is the HTTP status code. */
export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(options.headers as Record<string, string> | undefined),
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let res: Response
  try {
    res = await fetch(path, { ...options, headers })
  } catch {
    throw new ApiError(0, 'Network error. Check your connection and try again.')
  }

  if (!res.ok) {
    let detail = res.statusText || `Request failed with status ${res.status}`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body && typeof body.detail === 'string' && body.detail.trim()) {
        detail = body.detail
      }
    } catch {
      // Body wasn't JSON (or was empty) — fall back to the status text above.
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) {
    return undefined as T
  }
  return (await res.json()) as T
}

/** POST /api/sessions — creates a new session. No auth header, no body. */
export function createSession(): Promise<CreateSessionResponse> {
  return request('/api/sessions', { method: 'POST' })
}

/** GET /api/sessions/{id} */
export function getSession(
  sessionId: string,
  token: string,
): Promise<SessionViewResponse> {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: 'GET' }, token)
}

/** POST /api/sessions/{id}/messages */
export function postMessage(
  sessionId: string,
  token: string,
  text: string,
): Promise<SessionViewResponse> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/messages`,
    { method: 'POST', body: JSON.stringify({ text }) },
    token,
  )
}

/** POST /api/sessions/{id}/actions */
export function postAction(
  sessionId: string,
  token: string,
  action: ActionType,
): Promise<SessionViewResponse> {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/actions`,
    { method: 'POST', body: JSON.stringify({ action }) },
    token,
  )
}

/** GET /api/health — unauthenticated status probe. */
export function getHealth(): Promise<HealthResponse> {
  return request('/api/health', { method: 'GET' })
}

// --- Session persistence (localStorage) -------------------------------

const STORAGE_KEY = 'claims-assistant.session'

export function loadStoredSession(): StoredSession | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<StoredSession>
    if (typeof parsed.session_id === 'string' && typeof parsed.token === 'string') {
      return { session_id: parsed.session_id, token: parsed.token }
    }
    return null
  } catch {
    return null
  }
}

export function saveStoredSession(session: StoredSession): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch {
    // localStorage may be unavailable (private browsing, quota, etc.); the
    // app still works for the current tab, it just won't persist a reload.
  }
}

export function clearStoredSession(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
