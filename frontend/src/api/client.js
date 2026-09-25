const BASE = '/api'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

export async function request(path, { body, ...options } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') message = data.detail
      else if (Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join('; ')
    } catch {
      // 非 JSON 响应，保留状态码信息
    }
    throw new ApiError(res.status, message)
  }
  return res.status === 204 ? null : res.json()
}

export const getHealth = () => request('/health')
