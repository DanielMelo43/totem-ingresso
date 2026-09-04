const API_URL = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/$/, '')

export class PublicApiError extends Error {
  status: number
  code: string
  constructor(message = 'Não foi possível concluir a operação. Tente novamente.', status = 0, code = 'NETWORK_ERROR') {
    super(message)
    this.name = 'PublicApiError'
    this.status = status
    this.code = code
  }
}

/** Cliente da API FastAPI: envia JSON e nunca repassa detalhes técnicos à interface. */
export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!/^\/[a-z0-9/_?=&.-]*$/i.test(path)) throw new PublicApiError()
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 10_000)
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: controller.signal,
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...options.headers },
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => null) as {erro?:{codigo?:string;mensagem?:string}} | null
      throw new PublicApiError(payload?.erro?.mensagem, response.status, payload?.erro?.codigo)
    }
    return await response.json() as T
  } catch (error) {
    if (import.meta.env.DEV) console.error('Falha na API:', error)
    throw error instanceof PublicApiError ? error : new PublicApiError()
  } finally {
    window.clearTimeout(timeout)
  }
}

function deviceId() {
  const storageKey = 'totem-device-id'
  let value = window.localStorage.getItem(storageKey)
  if (!value) {
    value = `totem-${crypto.randomUUID()}`
    window.localStorage.setItem(storageKey, value)
  }
  return value
}

/** Escritas são idempotentes e repetidas somente se a conexão falhar. */
export async function apiMutation<T>(path:string, body:unknown, key:string=crypto.randomUUID()):Promise<T> {
  const options:RequestInit = {method:'POST', body:JSON.stringify(body), headers:{'Idempotency-Key':key,'X-Device-ID':deviceId()}}
  try {
    return await apiRequest<T>(path, options)
  } catch (error) {
    if (error instanceof PublicApiError && error.status === 0) return apiRequest<T>(path, options)
    throw error
  }
}

/** Complemento de UX; o rate limit real deve ser aplicado por IP/dispositivo no backend. */
export function createAttemptLimiter(limit = 10, windowMs = 60_000) {
  const attempts: number[] = []
  return () => {
    const now = Date.now()
    while (attempts.length && attempts[0] <= now - windowMs) attempts.shift()
    if (attempts.length >= limit) return false
    attempts.push(now)
    return true
  }
}
