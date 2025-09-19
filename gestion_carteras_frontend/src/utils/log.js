import { getLocalDateString } from './date.js'

const KEY = 'debug_download_log'

export function logDownload(event, payload) {
  try {
    const arr = JSON.parse(localStorage.getItem(KEY) || '[]')
    arr.push({ ts: getLocalDateString(), event, payload })
    // limitar a 200 entradas
    while (arr.length > 200) arr.shift()
    localStorage.setItem(KEY, JSON.stringify(arr))
  } catch {}
}

export function getDownloadLog() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') } catch { return [] }
}

export function clearDownloadLog() {
  try { localStorage.removeItem(KEY) } catch {}
}


