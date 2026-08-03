import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('oa_token') || '',
    user: JSON.parse(localStorage.getItem('oa_user') || 'null'),
    permissions: {},
    uiPermissions: [],
    bootstrapped: false
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    can: (state) => (module, action) => (state.permissions[module] || []).includes(action),
    canAny: (state) => (module, actions) => actions.some((action) => (state.permissions[module] || []).includes(action)),
    canUi: (state) => (key) => state.user?.role === 'admin' || (state.uiPermissions || []).includes(key)
  },
  actions: {
    setSession(data) {
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('oa_token', data.access_token)
      localStorage.setItem('oa_user', JSON.stringify(data.user))
    },
    async login(payload) {
      const { data } = await api.post('/auth/login', payload)
      this.setSession(data)
      if (data.user?.must_reset_password) {
        this.permissions = {}
        this.uiPermissions = []
        this.bootstrapped = true
        return data
      }
      await this.loadHomepage()
      return data
    },
    async loadHomepage() {
      const { data } = await api.get('/homepage')
      this.user = data.user
      this.permissions = data.permissions || {}
      this.uiPermissions = data.ui_permissions || []
      localStorage.setItem('oa_user', JSON.stringify(data.user))
      this.bootstrapped = true
      return data
    },
    async bootstrap() {
      if (!this.token || this.bootstrapped) return
      const { data } = await api.get('/auth/me')
      this.user = data
      localStorage.setItem('oa_user', JSON.stringify(data))
      if (data.must_reset_password) {
        this.permissions = {}
        this.uiPermissions = []
        this.bootstrapped = true
        return
      }
      await this.loadHomepage()
    },
    async changePassword(payload) {
      const { data } = await api.post('/auth/password/change', payload)
      this.user = data
      localStorage.setItem('oa_user', JSON.stringify(data))
      await this.loadHomepage()
    },
    async logout() {
      try {
        await api.post('/auth/logout')
      } finally {
        this.token = ''
        this.user = null
        this.permissions = {}
        this.uiPermissions = []
        this.bootstrapped = false
        localStorage.removeItem('oa_token')
        localStorage.removeItem('oa_user')
      }
    }
  }
})
