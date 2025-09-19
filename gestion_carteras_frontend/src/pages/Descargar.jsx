import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client.js'
import { getCurrentRoleAndEmpleado } from '../utils/jwt.js'
import { formatDateYYYYMMDD, getLocalDateString } from '../utils/date.js'
import { tarjetasStore } from '../state/store.js'
import { offlineDB } from '../offline/db.js'
import { computeDerived } from '../utils/derive.js'
import { logDownload } from '../utils/log.js'

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

  async function enrichTarjetasWithResumen(tarjetas) {
    const hoy = new Date()
    logDownload('tarjetas_raw', { total: tarjetas?.length || 0, sample: (tarjetas||[]).slice(0,3) })
    const enriched = await Promise.all(tarjetas.map(async (t) => {
      // completar datos de cliente si falta CUALQUIER campo clave (incluye teléfono)
      try {
        if (t?.cliente_identificacion) {
          const needCliente = !t?.cliente?.nombre || !t?.cliente?.apellido || !t?.cliente?.telefono || !t?.cliente?.direccion
          if (needCliente) {
            const cli = await apiClient.getClienteByIdentificacion(t.cliente_identificacion)
            t.cliente = t.cliente || {}
            t.cliente.nombre = cli?.nombre || t.cliente.nombre
            t.cliente.apellido = cli?.apellido || t.cliente.apellido
            t.cliente.telefono = cli?.telefono || t.cliente.telefono
            t.cliente.direccion = cli?.direccion || t.cliente.direccion
            // refuerzos a nivel raíz por compatibilidad en UI
            t.telefono = t.telefono || cli?.telefono || t?.cliente?.telefono
            t.cliente_telefono = t.cliente_telefono || cli?.telefono || t?.cliente?.telefono
            // identificación en objeto cliente si no viene
            if (!t?.cliente?.identificacion && t?.cliente_identificacion) t.cliente.identificacion = t.cliente_identificacion
            logDownload('cliente_completado', { tarjeta: t.codigo, cliente_identificacion: t.cliente_identificacion, cliente: cli })
          }
        }
      } catch {}
      // obtener abonos para derivar el resumen localmente
      let abonos = []
      try {
        abonos = await apiClient.getAbonosByTarjeta(t.codigo)
        logDownload('abonos_tarjeta', { tarjeta: t.codigo, num: (abonos||[]).length, sample: (abonos||[]).slice(0,3) })
      } catch { abonos = [] }
      // guardar abonos offline por tarjeta
      try { await offlineDB.setAbonos(t.codigo, abonos) } catch {}
      // computar resumen derivado localmente
      const resumen = computeDerived(t, abonos, hoy)
      const enrichedT = { ...t, resumen }
      logDownload('tarjeta_enriched', { tarjeta: t.codigo, resumen })
      return enrichedT
    }))
    return enriched
  }

  async function descargarParaEmpleado(id) {
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
      if (!(canByDate && canDownload)) {
        setError('Descarga no permitida hoy. Solicita habilitación si es necesario.')
        return
      }
    } catch (e) {
      setError(e?.message || 'No se pudo verificar permisos de descarga')
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
              const d = a?.fecha ? new Date(a.fecha) : (a?.ts ? new Date(a.ts): null)
              const isToday = d && formatDateYYYYMMDD(d) === hoy
              return isToday ? s + Number(a?.monto||0) : s
            }, 0)
            const countHoy = (list||[]).filter(a=>{
              const d = a?.fecha ? new Date(a.fecha) : (a?.ts ? new Date(a.ts): null)
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
      setError(e?.message || 'Error al descargar')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (role === 'admin') {
      apiClient.getEmpleados().then(setEmpleados).catch((e) => setError(e?.message || 'Error cargando empleados'))
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
