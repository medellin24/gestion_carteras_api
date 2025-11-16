/**
 * Utilidades para manejo de fechas en zona horaria local
 */

/**
 * Obtiene la fecha actual en formato YYYY-MM-DD usando la zona horaria local
 * @returns {string} Fecha en formato YYYY-MM-DD
 */
export function getLocalDateString() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Convierte una fecha a string en formato YYYY-MM-DD usando zona horaria local
 * @param {Date} date - Fecha a convertir
 * @returns {string} Fecha en formato YYYY-MM-DD
 */
export function toLocalDateString(date) {
  if (!date) return getLocalDateString()
  
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Formatea una fecha a string en formato YYYY-MM-DD usando zona horaria local
 * Si no se proporciona fecha, usa la fecha actual
 * @param {Date} [date] - Fecha a formatear (opcional)
 * @returns {string} Fecha en formato YYYY-MM-DD
 */
export function formatDateYYYYMMDD(date) {
  if (!date) return getLocalDateString()
  
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Detecta si una cadena es YYYY-MM-DD
 * @param {string} str
 * @returns {boolean}
 */
export function isYYYYMMDD(str) {
  return typeof str === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(str)
}

/**
 * Parsea una fecha ISO a Date en zona local, tratando YYYY-MM-DD como fecha local (no UTC)
 * @param {string} dateStr
 * @returns {Date|null}
 */
export function parseISODateToLocal(dateStr) {
  if (!dateStr) return null
  try {
    // 1) YYYY-MM-DD => interpretar como fecha local (00:00 local)
    if (isYYYYMMDD(dateStr)) {
      const [y, m, d] = dateStr.split('-').map(Number)
      return new Date(y, m - 1, d)
    }
    // 2) ISO con zona explícita (Z o +/-hh:mm) => usar parser nativo
    if (/[zZ]|[+\-]\d{2}:\d{2}$/.test(dateStr)) {
      const d = new Date(dateStr)
      return isNaN(d.getTime()) ? null : d
    }
    // 3) ISO con 'T' y SIN zona => tratar como UTC naive (append 'Z')
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?$/.test(dateStr)) {
      const d = new Date(dateStr + 'Z')
      return isNaN(d.getTime()) ? null : d
    }
    // 4) Fallback
    const d = new Date(dateStr)
    return isNaN(d.getTime()) ? null : d
  } catch { return null }
}

/**
 * Normaliza distintos tipos (Date | number | string) a YYYY-MM-DD en zona local
 * - YYYY-MM-DD (string) se devuelve tal cual
 * - ISO con hora/offset -> se parsea y se formatea local
 * - timestamp number -> Date y se formatea local
 * @param {any} value
 * @returns {string}
 */
export function toYYYYMMDDLocal(value) {
  if (value == null) return getLocalDateString()
  if (value instanceof Date) return formatDateYYYYMMDD(value)
  if (typeof value === 'number') return formatDateYYYYMMDD(new Date(value))
  if (typeof value === 'string') {
    if (isYYYYMMDD(value)) return value
    const d = parseISODateToLocal(value)
    return d ? formatDateYYYYMMDD(d) : getLocalDateString()
  }
  try { return formatDateYYYYMMDD(new Date(value)) } catch { return getLocalDateString() }
}