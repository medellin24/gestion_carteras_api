const BASE_URL = (() => {
  // Aceptar ambas variantes y espacios
  const raw = (
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_BASE_API_URL ||
    ''
  ).trim()
  if (raw) {
    return raw.endsWith('/') ? raw.slice(0, -1) : raw
  }
  // En desarrollo, permitir localhost por conveniencia
  if (import.meta.env.DEV) return 'http://127.0.0.1:8000'
  // En producción/staging, fallar explícitamente si no está configurada
  throw new Error('VITE_API_BASE_URL no está configurada en el entorno de despliegue')
})()

class ApiError extends Error {
  constructor(message, { status, detail, body, headers, url, type } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status || null
    this.detail = detail
    this.body = body
    this.headers = headers
    this.url = url
    this.type = type || (status ? `http-${status}` : 'unknown')
  }
}

async function request(path, { method = 'GET', body, headers, timeoutMs } = {}) {
  const DEFAULT_TIMEOUT_MS = Number(import.meta.env.VITE_HTTP_TIMEOUT_MS || 120000)
  // Nunca lanzar por falta de BASE_URL en prod; ya tenemos fallback
  async function doFetch(withToken) {
    const accessToken = withToken ? localStorage.getItem('access_token') : null
    const finalHeaders = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(headers || {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    }
    const controller = new AbortController()
    const to = setTimeout(() => controller.abort(), Number(timeoutMs || DEFAULT_TIMEOUT_MS))
    try {
      const res = await fetch(`${BASE_URL}${path}`, {
        method,
        headers: finalHeaders,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })
      return res
    } finally {
      clearTimeout(to)
    }
  }

  // Primer intento con token actual (si existe)
  let res
  try {
    res = await doFetch(true)
  } catch (e) {
    const msg = String(e || '')
    if ((e && (e.name === 'AbortError' || msg.includes('AbortError'))) || msg.toLowerCase().includes('signal aborted')) {
      throw new ApiError('Timeout de solicitud. Verifica tu conexión e inténtalo de nuevo.', { type: 'timeout' })
    }
    if (msg.includes('Failed to fetch')) {
      throw new ApiError('No se pudo conectar con el servidor. Verifica tu conexión a internet.', { type: 'network' })
    }
    throw new ApiError('Error de red desconocido', { type: 'network' })
  }
  if (res.status === 401) {
    // Intentar refrescar y reintentar una vez
    try {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken })
        })
        if (refreshRes.ok) {
          const data = await refreshRes.json()
          if (data?.access_token) {
            localStorage.setItem('access_token', data.access_token)
          }
          if (data?.refresh_token) {
            localStorage.setItem('refresh_token', data.refresh_token)
          }
          if (data?.role) {
            localStorage.setItem('user_role', data.role)
          }
          // Reintentar con nuevo token
          res = await doFetch(true)
        } else {
          // Refresh falló: limpiar sesión para forzar login
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        }
      }
    } catch {
      // Si algo falla en refresh, continuar para arrojar error
    }
  }

  if (!res.ok) {
    const ct = res.headers.get('content-type') || ''
    let msg = 'Error de solicitud'
    let detail = null
    let body = null
    try {
      if (ct.includes('application/json')) {
        const data = await res.json()
        body = data
        const _detail = data?.detail
        if (Array.isArray(_detail)) {
          // Formato de validación de FastAPI (422)
          msg = _detail.map(e => {
            const loc = Array.isArray(e.loc) ? e.loc.join('.') : ''
            return `${loc ? loc + ': ' : ''}${e.msg || String(e)}`
          }).join(' | ')
          detail = _detail
        } else if (typeof _detail === 'string') {
          msg = _detail
          detail = _detail
        } else if (_detail && typeof _detail === 'object') {
          msg = (_detail.message || _detail.error || JSON.stringify(_detail))
          detail = _detail
        } else {
          msg = data?.message || data?.error || JSON.stringify(data)
          detail = data
        }
      } else {
        const txt = await res.text()
        msg = txt || msg
        body = txt
      }
    } catch {
      // Si falla el parseo, dejar msg por defecto
    }
    throw new ApiError(msg, { status: res.status, detail, body, headers: Object.fromEntries(res.headers.entries()), url: `${BASE_URL}${path}`, type: `http-${res.status}` })
  }
  const contentType = res.headers.get('content-type') || ''
  return contentType.includes('application/json') ? res.json() : res.text()
}

export const apiClient = {
  login: async ({ username, password }) => {
    return request('/auth/login', { method: 'POST', body: { username, password } })
  },
  refresh: async (refreshToken) => {
    return request('/auth/refresh', { method: 'POST', body: { refresh_token: refreshToken } })
  },
  getEmpleados: async () => {
    return request('/empleados/', { method: 'GET' })
  },
  getTarjetasByEmpleado: async (empleadoId, estado = 'activas', skip = 0, limit = 500) => {
    const params = new URLSearchParams({ estado, skip: String(skip), limit: String(limit) })
    return request(`/empleados/${encodeURIComponent(empleadoId)}/tarjetas/?${params.toString()}`, { method: 'GET' })
  },
  getAbonosDiaByEmpleado: async (empleadoId, yyyyMmDd) => {
    return request(`/empleados/${encodeURIComponent(empleadoId)}/abonos/${yyyyMmDd}`, { method: 'GET' })
  },
  getTarjetaResumen: async (tarjetaCodigo) => {
    return request(`/tarjetas/${encodeURIComponent(tarjetaCodigo)}/resumen`, { method: 'GET' })
  },
  getClienteByIdentificacion: async (identificacion) => {
    return request(`/clientes/${encodeURIComponent(identificacion)}`, { method: 'GET' })
  },
  createCliente: async ({ identificacion, nombre, apellido, telefono, direccion, observaciones }) => {
    return request('/clientes/', { method: 'POST', body: { identificacion, nombre, apellido, telefono, direccion, observaciones } })
  },
  updateCliente: async (identificacion, { nombre, apellido, telefono, direccion, observaciones }) => {
    return request(`/clientes/${encodeURIComponent(identificacion)}`, { method: 'PUT', body: { nombre, apellido, telefono, direccion, observaciones } })
  },
  getClienteHistorial: async (identificacion) => {
    return request(`/clientes/${encodeURIComponent(identificacion)}/historial`, { method: 'GET' })
  },
  getClienteEstadisticas: async (identificacion) => {
    return request(`/clientes/${encodeURIComponent(identificacion)}/estadisticas`, { method: 'GET' })
  },
  getTarjeta: async (codigo) => {
    return request(`/tarjetas/${encodeURIComponent(codigo)}`, { method: 'GET' })
  },
  getAbonosByTarjeta: async (codigo) => {
    return request(`/tarjetas/${encodeURIComponent(codigo)}/abonos/`, { method: 'GET' })
  },
  crearAbono: async ({ tarjeta_codigo, monto, metodo_pago }) => {
    return request('/abonos/', { method: 'POST', body: { tarjeta_codigo, monto, metodo_pago } })
  },
  eliminarUltimoAbono: async (tarjetaCodigo) => {
    return request(`/tarjetas/${encodeURIComponent(tarjetaCodigo)}/abonos/ultimo`, { method: 'DELETE' })
  },
  crearTarjeta: async ({ cliente_identificacion, empleado_identificacion, monto, cuotas, interes, numero_ruta, observaciones, posicion_anterior, posicion_siguiente }) => {
    return request('/tarjetas/', { method: 'POST', body: { cliente_identificacion, empleado_identificacion, monto, cuotas, interes, numero_ruta, observaciones, posicion_anterior, posicion_siguiente } })
  },
  sync: async (payload) => {
    try {
      // request() devuelve contenido parseado, no objeto Response
      const result = await request('/sync', { method: 'POST', body: payload, timeoutMs: 120000 })
      const alreadyProcessed = Boolean(result?.already_processed)
      const createdTarjetas = Number(result?.created_tarjetas?.length || 0)
      const createdAbonos = Number(result?.created_abonos?.length || 0)
      const createdGastos = Number(result?.created_gastos || 0)
      const createdBases = Number(result?.created_bases || 0)
      const total = createdTarjetas + createdAbonos + createdGastos + createdBases

      const summary = alreadyProcessed
        ? 'Operación repetida (idempotente): no se procesaron cambios nuevos.'
        : `Sincronización completada: ${total} cambios (Tarjetas: ${createdTarjetas}, Abonos: ${createdAbonos}, Gastos: ${createdGastos}, Bases: ${createdBases}).`
      return {
        success: true,
        status: 200,
        message: summary,
        data: result
      }
      
    } catch (error) {
      // Manejar diferentes tipos de errores específicamente
      const err = error || {}
      const status = err.status || null
      const errType = err.type || 'unknown'
      const errorMessage = err.message || 'Error desconocido'

      // 1) Timeout / Red
      if (errType === 'timeout') {
        return { success: false, status, type: 'timeout', message: 'Tiempo de espera agotado. Verifica tu conexión y vuelve a intentar.' }
      }
      if (errType === 'network') {
        return { success: false, status, type: 'network', message: 'No hay conexión con el servidor. Revisa tu internet o VPN.' }
      }

      // 2) HTTP con códigos
      if (status === 403) {
        const detail = (err.detail && (err.detail.message || err.detail.error || err.detail)) || errorMessage
        // Mensajes específicos
        if (String(detail).toLowerCase().includes('permiso') && String(detail).toLowerCase().includes('subida')) {
          return { success: false, status, type: 'permission', message: 'Empleado sin permiso de subida habilitado para hoy.' }
        }
        if (String(detail).toLowerCase().includes('ya realizó una subida')) {
          return { success: false, status, type: 'daily-limit', message: 'Ya se realizó una subida hoy. Disponible nuevamente mañana.' }
        }
        return { success: false, status, type: 'forbidden', message: `Acceso denegado: ${detail}` }
      }
      if (status === 400) {
        const detail = (err.detail && (err.detail.message || err.detail.error || err.detail)) || errorMessage
        if (String(detail).toLowerCase().includes('múltiples empleados')) {
          return { success: false, status, type: 'multiple-employees', message: 'No se puede sincronizar datos de múltiples empleados en una sola operación.' }
        }
        return { success: false, status, type: 'bad-request', message: `Datos inválidos: ${detail}` }
      }
      if (status === 404) {
        return { success: false, status, type: 'not-found', message: 'Recurso no encontrado (p.ej., empleado desconocido).' }
      }
      if (status === 422) {
        return { success: false, status, type: 'validation', message: 'Error de validación en los datos enviados.' }
      }
      if (status === 500) {
        return { success: false, status, type: 'server', message: 'Error interno del servidor. Inténtalo más tarde o contacta al administrador.' }
      }

      // 3) Genérico
      return { success: false, status, type: errType || 'sync', message: errorMessage }
    }
  },
  // Permisos basados en columnas de empleado (descargar, subir, fecha_accion)
  getEmpleadoPermissions: async (empleadoId) => {
    return request(`/empleados/${encodeURIComponent(empleadoId)}/permissions`, { method: 'GET' })
  },
  setEmpleadoPermissions: async (empleadoId, perms) => {
    // perms: { descargar?: boolean, subir?: boolean, fecha_accion?: string(YYYY-MM-DD) }
    return request(`/empleados/${encodeURIComponent(empleadoId)}/permissions`, { method: 'POST', body: perms })
  },
}
export { request }
