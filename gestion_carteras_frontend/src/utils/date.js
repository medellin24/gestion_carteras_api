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