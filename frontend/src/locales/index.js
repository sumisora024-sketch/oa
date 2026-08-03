import { createI18n } from 'vue-i18n'

import en from './en'
import ja from './ja'
import zh from './zh'

const saved = localStorage.getItem('oa_locale') || 'ja'

export default createI18n({
  legacy: false,
  locale: saved,
  fallbackLocale: 'ja',
  messages: { zh, ja, en }
})
