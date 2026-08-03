import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true
})

const unsafeMethods = new Set(['post', 'put', 'patch', 'delete'])
const pendingMutations = new Map()

function mutationSignature(config) {
  const method = String(config.method || 'get').toLowerCase()
  if (!unsafeMethods.has(method)) return null
  const url = `${config.baseURL || ''}${config.url || ''}`
  const params = config.params ? JSON.stringify(config.params) : ''
  if (config.data instanceof FormData) {
    const parts = []
    for (const [key, value] of config.data.entries()) {
      if (value instanceof File) {
        parts.push([key, value.name, value.size, value.lastModified])
      } else {
        parts.push([key, value])
      }
    }
    return `${method}:${url}:${params}:${JSON.stringify(parts)}`
  }
  const data = typeof config.data === 'string' ? config.data : JSON.stringify(config.data || {})
  return `${method}:${url}:${params}:${data}`
}

function idempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('oa_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const signature = mutationSignature(config)
  if (signature) {
    if (pendingMutations.has(signature)) {
      const error = new Error('duplicate mutation request')
      error.isDuplicateMutation = true
      return Promise.reject(error)
    }
    pendingMutations.set(signature, true)
    config.metadata = { ...(config.metadata || {}), mutationSignature: signature }
    config.headers['Idempotency-Key'] = config.headers['Idempotency-Key'] || idempotencyKey()
  }
  return config
})

api.interceptors.response.use(
  (response) => {
    const signature = response.config?.metadata?.mutationSignature
    if (signature) pendingMutations.delete(signature)
    return response
  },
  (error) => {
    const signature = error.config?.metadata?.mutationSignature
    if (signature) pendingMutations.delete(signature)
    if (error.response?.status === 401 && location.pathname !== '/login') {
      localStorage.removeItem('oa_token')
      localStorage.removeItem('oa_user')
      location.href = '/login'
    }
    return Promise.reject(error)
  }
)
