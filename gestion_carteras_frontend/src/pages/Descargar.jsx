import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client.js'
import { getCurrentRoleAndEmpleado } from '../utils/jwt.js'
import { formatDateYYYYMMDD, getLocalDateString, parseISODateToLocal } from '../utils/date.js'
import { tarjetasStore } from '../state/store.js'
import { offlineDB } from '../offline/db.js'
import { computeDerived } from '../utils/derive.js'
import { logDownload } from '../utils/log.js'
import { persistPlanInfoFromLimits } from '../utils/plan.js'

function Loading({ message }) {
  return (
    <div className="card" style={{maxWidth: 680, textAlign:'center'}}>
      <strong>{message}</strong>
      <span style={{color:'var(--muted)'}}>Descargando tarjetas, por favor espera…</span>
    </div>
  )
}

export default function DescargarPage() {
  const navigate = useNavigate()
  const [{ role, empleadoId }] = useState(getCurrentRoleAndEmpleado())
  const [empleados, setEmpleados] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const authRedirectRef = useRef(false)

  const handleUnauthorized = (err, action = 'continuar') => {
    if (err?.status === 401) {
      if (!authRedirectRef.current) {
        authRedirectRef.current = true
        setError(`Sesión expirada. Inicia sesión nuevamente para ${action}.`)
        setTimeout(() => navigate('/login'), 400)
      } else {
        setError('Sesión expirada. Ingresa de nuevo.')
      }
      return true
    }
    return false
  }

  // Función auxiliar para reintentos con backoff exponencial
  async function retryOperation(operation, retries = 3, delay = 1000) {
    try {
      return await operation()
    } catch (err) {
      if (retries <= 0) throw err
      await new Promise(resolve => setTimeout(resolve, delay))
      return retryOperation(operation, retries - 1, delay * 1.5)
    }
  }

  // Función auxiliar para procesar en lotes (concurrency limit)
  async function processInBatches(items, batchSize, fn) {
    const results = []
    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize)
      const batchResults = await Promise.all(batch.map(fn))
      results.push(...batchResults)
    }
    return results
  }

  async function enrichTarjetasWithResumen(tarjetas) {
    const hoy = new Date()
    logDownload('tarjetas_raw', { total: tarjetas?.length || 0, sample: (tarjetas||[]).slice(0,3) })
    
    // Procesar en lotes de 5 para evitar saturación de red en Android y timeouts
    const enriched = await processInBatches(tarjetas, 5, async (t) => {
      // 1. Completar datos de cliente
      try {
        if (t?.cliente_identificacion) {
          const needCliente = !t?.cliente?.nombre || !t?.cliente?.apellido || !t?.cliente?.telefono || !t?.cliente?.direccion
          if (needCliente) {
            // Reintentar obtención de cliente si falla
            await retryOperation(async () => {
              const cli = await apiClient.getClienteByIdentificacion(t.cliente_identificacion)
              t.cliente = t.cliente || {}
              t.cliente.nombre = cli?.nombre || t.cliente.nombre
              t.cliente.apellido = cli?.apellido || t.cliente.apellido
              t.cliente.telefono = cli?.telefono || t.cliente.telefono
              t.cliente.direccion = cli?.direccion || t.cliente.direccion
              t.telefono = t.telefono || cli?.telefono || t?.cliente?.telefono
              t.cliente_telefono = t.cliente_telefono || cli?.telefono || t?.cliente?.telefono
              if (!t?.cliente?.identificacion && t?.cliente_identificacion) t.cliente.identificacion = t.cliente_identificacion
            }, 2, 500)
            logDownload('cliente_completado', { tarjeta: t.codigo, cliente_identificacion: t.cliente_identificacion })
          }
        }
      } catch (e) {
        console.warn(`No se pudo completar info de cliente para ${t.codigo}`, e)
        // No es crítico, continuamos
      }

      // 2. Obtener abonos (CRÍTICO: Con reintentos y fallo explícito)
      let abonos = []
      try {
        abonos = await retryOperation(async () => {
          return await apiClient.getAbonosByTarjeta(t.codigo)
        }, 3, 1000) // 3 intentos, espera inicial 1s
        
        logDownload('abonos_tarjeta', { tarjeta: t.codigo, num: (abonos||[]).length })
      } catch (err) {
        // Si falla después de 3 reintentos, ES UN ERROR REAL DE RED.
        // NO debemos asumir abonos=[], porque eso corrompe el saldo.
        // Lanzamos el error para detener la descarga completa.
        console.error(`Fallo crítico descargando abonos tarjeta ${t.codigo}`, err)
        throw new Error(`Error de red descargando abonos de tarjeta ${t.codigo}. Revisa tu conexión.`)
      }

      // 3. Guardar abonos offline
      try { await offlineDB.setAbonos(t.codigo, abonos) } catch {}
      
      // 4. Computar resumen
      const resumen = computeDerived(t, abonos, hoy)
      const enrichedT = { ...t, resumen }
      return enrichedT
    })
    
    return enriched
  }

  async function descargarParaEmpleado(id) {
    // Verificar estado de suscripción de la cuenta (bloquear si vencida)
    try {
      const limits = await apiClient.getLimits()
      const planSnapshot = persistPlanInfoFromLimits(limits)
      const remaining = Number(planSnapshot?.remaining ?? limits?.days_remaining ?? 0)
      if (remaining <= 0) {
        setError('Suscripción vencida. Renueva tu plan para continuar.')
        return
      }
    } catch (e) {
      if (handleUnauthorized(e, 'validar la suscripción')) return
      if (e && e.status === 403) {
        setError(e?.message || 'Suscripción vencida o no activa. Renueva para continuar.')
        return
      }
      setError(e?.message || 'No se pudo validar la suscripción. Inténtalo más tarde.')
      return
    }
    // Validación de límite por plan (empleados distintos por día)
    try {
      const attempt = await apiClient.attemptDownload(id)
      if (!attempt?.allowed) {
        const baseMsg = attempt?.message || 'Límite diario alcanzado para el plan.'
        const used = typeof attempt?.used === 'number' ? attempt.used : 0
        const limit = typeof attempt?.limit === 'number' ? attempt.limit : 1
        setError(`${baseMsg} (${used}/${limit}).`)
        return
      }
    } catch (e) {
      if (handleUnauthorized(e, 'registrar la descarga diaria')) return
      if (e?.status === 403) {
        setError(e?.message || 'No tienes permiso para registrar esta descarga.')
        return
      }
      if (e?.status === 404) {
        setError('No se encontró la cuenta asociada para validar el intento de descarga.')
        return
      }
      setError(e?.message || 'No se pudo validar el límite del plan. Inténtalo de nuevo más tarde o contacta al administrador.')
      return
    }
    const hoy = formatDateYYYYMMDD()
    try { 
      localStorage.setItem('empleado_identificacion', String(id))
      // Buscar el nombre del empleado en la lista
      const empleado = empleados.find(e => e.identificacion === id)
      if (empleado) {
        localStorage.setItem('empleado_nombre', empleado.nombre_completo || empleado.nombre || id)
      } else {
        // Si no se encuentra en la lista, usar el ID como nombre
        localStorage.setItem('empleado_nombre', String(id))
      }
      // Disparar evento para notificar que se seleccionó un empleado
      window.dispatchEvent(new Event('empleado-selected'))
    } catch {}
    // Verificar permiso con columnas del empleado: descargar, subir, fecha_accion
    try {
      const perms = await apiClient.getEmpleadoPermissions(id)
      const today = getLocalDateString()
      const last = String(perms?.fecha_accion || '')
      const canByDate = !last || last < today // si fecha_accion es anterior a hoy
      const canDownload = Boolean(perms?.descargar)
      if (!canDownload) {
        setError('Descarga deshabilitada para este cobrador. Solicita al administrador que habilite el permiso.')
        return
      }
      if (!canByDate) {
        setError('Ya realizaste una descarga hoy. Podrás volver a descargar mañana.')
        return
      }
    } catch (e) {
      if (handleUnauthorized(e, 'verificar permisos de descarga')) return
      setError(e?.message || 'No se pudo verificar permisos de descarga. Reintenta en unos minutos.')
      return
    }
    setLoading(true)
    setError('')
    try {
      // Limpiar outbox antes de descargar para tener área de trabajo limpia
      try {
        const outbox = await offlineDB.readOutbox()
        await Promise.all(outbox.map(item => offlineDB.removeOutbox(item.id)))
        console.log('Outbox limpiado antes de descargar')
      } catch (e) {
        console.warn('Error limpiando outbox:', e)
      }
      
      const tarjetas = await apiClient.getTarjetasByEmpleado(id, 'activas')
      logDownload('tarjetas_empleado', { empleado: id, total: tarjetas?.length || 0 })
      const enriched = await enrichTarjetasWithResumen(tarjetas)
      // Recaudado del día
      let stats = { monto: 0, abonos: 0 }
      try {
        // derivar stats del día sumando abonos del día por tarjeta offline
        const sums = await Promise.all(enriched.map(async (t) => {
          try {
            const list = await offlineDB.getAbonos(t.codigo)
            const today = hoy
            const ymd = String(today)
            const totalHoy = (list||[]).reduce((s,a)=>{
              const d = a?.fecha ? parseISODateToLocal(String(a.fecha)) : (a?.ts ? new Date(a.ts): null)
              const isToday = d && formatDateYYYYMMDD(d) === hoy
              return isToday ? s + Number(a?.monto||0) : s
            }, 0)
            const countHoy = (list||[]).filter(a=>{
              const d = a?.fecha ? parseISODateToLocal(String(a.fecha)) : (a?.ts ? new Date(a.ts): null)
              return d && formatDateYYYYMMDD(d) === hoy
            }).length
            return { monto: totalHoy, abonos: countHoy }
          } catch { return { monto: 0, abonos: 0 } }
        }))
        stats = sums.reduce((acc, s) => ({ monto: acc.monto + s.monto, abonos: acc.abonos + s.abonos }), { monto: 0, abonos: 0 })
      } catch {}
      tarjetasStore.saveTarjetas(enriched)
      tarjetasStore.saveStats(stats)
      logDownload('stats', stats)
      await offlineDB.setTarjetas(enriched)
      await offlineDB.setStats(stats)
      // Consumir permiso: descargar=false, subir=true (sin tocar fecha_accion aún)
      try { await apiClient.setEmpleadoPermissions(id, { descargar: false, subir: true }) } catch {}
      tarjetasStore.markDownload(id, hoy)
      navigate('/tarjetas')
    } catch (e) {
      if (handleUnauthorized(e, 'descargar tarjetas')) return
      setError(e?.message || 'Error al descargar')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (role === 'admin') {
      apiClient.getEmpleados()
        .then(setEmpleados)
        .catch((e) => {
          if (handleUnauthorized(e, 'listar cobradores')) return
          setError(e?.message || 'Error cargando empleados')
        })
    } else if (role === 'cobrador' && empleadoId) {
      // Para cobradores, obtener la información del empleado desde el JWT o localStorage
      const empleadoNombre = localStorage.getItem('empleado_nombre') || empleadoId
      localStorage.setItem('empleado_identificacion', empleadoId)
      localStorage.setItem('empleado_nombre', empleadoNombre)
      // Disparar evento para notificar que se seleccionó un empleado
      window.dispatchEvent(new Event('empleado-selected'))
      descargarParaEmpleado(empleadoId)
    }
  }, [])

  return (
    <div className="app-shell">
      <header className="app-header"><h1>Descargar tarjetas</h1></header>
      <main style={{width:'100%'}}>
        {loading ? <Loading message="Sincronizando" /> : (
          <div style={{width:'100%', maxWidth:680}}>
            {error && <div className="error" role="alert">{error}</div>}
            {role === 'admin' ? (
              <div className="card">
                <strong>Selecciona un cobrador</strong>
                <div style={{display:'flex', flexDirection:'column', gap:10}}>
                  {empleados.map((e) => (
                    <button key={e.identificacion} className="primary" onClick={() => descargarParaEmpleado(e.identificacion)}>
                      {e.nombre_completo || e.nombre} — {e.identificacion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="card"><strong>Preparado para descargar</strong><span style={{color:'var(--muted)'}}>Presiona para actualizar si no inició automáticamente.</span><button className="primary" onClick={() => descargarParaEmpleado(empleadoId)}>Descargar ahora</button></div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}


