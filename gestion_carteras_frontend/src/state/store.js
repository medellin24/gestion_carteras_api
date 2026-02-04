const STORAGE_KEYS = {
  tarjetas: 'tarjetas_data',
  stats: 'tarjetas_stats',
  lastDownload: 'tarjetas_last_download',
  viewMode: 'tarjetas_view_mode',
}

export const tarjetasStore = {
  setViewMode(mode) { // 'cards' | 'list'
    localStorage.setItem(STORAGE_KEYS.viewMode, mode)
  },
  getViewMode() {
    return localStorage.getItem(STORAGE_KEYS.viewMode) || 'cards'
  },
  saveTarjetas(list) {
    localStorage.setItem(STORAGE_KEYS.tarjetas, JSON.stringify(list || []))
  },
  getTarjetas() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.tarjetas) || '[]') } catch { return [] }
  },
  saveStats(stats) {
    localStorage.setItem(STORAGE_KEYS.stats, JSON.stringify(stats || { monto: 0, abonos: 0 }))
  },
  getStats() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.stats) || '{"monto":0,"abonos":0}') } catch { return { monto: 0, abonos: 0 } }
  },
  markDownload(empleadoId, yyyymmdd) {
    const key = `${empleadoId}:${yyyymmdd}`
    const map = this._readLastDownload()
    map[key] = true
    localStorage.setItem(STORAGE_KEYS.lastDownload, JSON.stringify(map))
  },
  canDownload(empleadoId, yyyymmdd) {
    const key = `${empleadoId}:${yyyymmdd}`
    const map = this._readLastDownload()
    return !map[key]
  },
  _readLastDownload() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.lastDownload) || '{}') } catch { return {} }
  }
}
