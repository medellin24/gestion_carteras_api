import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { offlineDB } from '../offline/db.js'
import { getLocalDateString } from '../utils/date.js'
import { apiClient } from '../api/client.js'
import { Edit, Trash2, Check, X } from 'lucide-react'

export default function SubirPage(){
  const [pending, setPending] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('info') // 'success', 'error', 'info'
  const [outboxData, setOutboxData] = useState({ tarjetas: 0, abonos: 0, gastos: 0, bases: 0 })
  const [localGastos, setLocalGastos] = useState([])
  const [localBases, setLocalBases] = useState([])
  const navigate = useNavigate()
  const debugProfile = true

  function profiler(){
    const t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    const marks = []
    return {
      mark(label){ marks.push({ label, t: (typeof performance !== 'undefined' ? performance.now() : Date.now()) }) },
      table(){
        try {
          let prev = t0
          const rows = marks.map(m => { const d = Math.round(m.t - prev); prev = m.t; return { paso: m.label, ms: d } })
          rows.push({ paso: 'TOTAL', ms: Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0) })
          console.table(rows)
        } catch {}
      }
    }
  }

  async function refresh(){
    try {
      const outbox = await offlineDB.readOutbox()
      const currentEmpleadoId = localStorage.getItem('empleado_identificacion')
      
      if (!currentEmpleadoId) {
        setPending(0)
        setOutboxData({ tarjetas: 0, abonos: 0, gastos: 0, bases: 0 })
        setLocalGastos([])
        setLocalBases([])
        return
      }
      
      // Obtener las tarjetas del empleado actual para filtrar abonos
      const tarjetasEmpleado = await offlineDB.getTarjetas()
      const codigosTarjetasEmpleado = new Set(
        tarjetasEmpleado
          .filter(t => t.empleado_identificacion === currentEmpleadoId)
          .map(t => t.codigo)
      )
      
      // Filtrar solo los datos del empleado actualmente seleccionado
      const empleadoData = outbox.filter(item => {
        const itemEmpleadoId = item.empleado_identificacion || item.empleado_id
        
        // Para abonos, verificar que la tarjeta pertenezca al empleado actual
        if (item.type === 'abono:add') {
          return codigosTarjetasEmpleado.has(item.tarjeta_codigo)
        }
        
        // Para otros tipos, usar el empleado_identificacion
        return itemEmpleadoId === currentEmpleadoId
      })
      
      const count = empleadoData.length
      setPending(count)
      
      // Contar por tipo (solo del empleado actual)
      const data = {
        tarjetas: empleadoData.filter(item => item.type === 'tarjeta:new' && item.temp_id?.startsWith('tmp-')).length,
        abonos: empleadoData.filter(item => item.type === 'abono:add').length,
        gastos: empleadoData.filter(item => item.type === 'gasto:new').length,
        bases: empleadoData.filter(item => item.type === 'base:set').length,
      }
      setOutboxData(data)
      
      // Cargar gastos y bases locales para edición (solo del empleado actual)
      const gastos = empleadoData.filter(item => item.type === 'gasto:new')
      const bases = empleadoData.filter(item => item.type === 'base:set')
      setLocalGastos(gastos)
      setLocalBases(bases)
    } catch (e) {
      console.error('Error refreshing data:', e)
    }
  }

  useEffect(()=>{ refresh() }, [])

  function playSound(type = 'success') {
    try {
      // Crear un sonido simple usando Web Audio API
      const audioContext = new (window.AudioContext || window.webkitAudioContext)()
      const oscillator = audioContext.createOscillator()
      const gainNode = audioContext.createGain()
      
      oscillator.connect(gainNode)
      gainNode.connect(audioContext.destination)
      
      if (type === 'success') {
        // Sonido de éxito: dos tonos ascendentes
        oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime) // C5
        oscillator.frequency.setValueAtTime(659.25, audioContext.currentTime + 0.1) // E5
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3)
        oscillator.start(audioContext.currentTime)
        oscillator.stop(audioContext.currentTime + 0.3)
      } else if (type === 'error') {
        // Sonido de error: tono descendente
        oscillator.frequency.setValueAtTime(400, audioContext.currentTime)
        oscillator.frequency.setValueAtTime(200, audioContext.currentTime + 0.2)
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.4)
        oscillator.start(audioContext.currentTime)
        oscillator.stop(audioContext.currentTime + 0.4)
      }
    } catch (e) {
      // Si no se puede reproducir sonido, no hacer nada
      console.log('No se pudo reproducir sonido:', e)
    }
  }

  function showMessage(msg, type = 'info') {
    setMessage(msg)
    setMessageType(type)
    
    // Reproducir sonido según el tipo
    if (type === 'success') {
      playSound('success')
    } else if (type === 'error') {
      playSound('error')
    }
    
    // Duraciones: error 10s, success 10s, info 5s
    const duration = type === 'error' ? 10000 : (type === 'success' ? 10000 : 5000)
    setTimeout(() => setMessage(''), duration)
  }

  async function handleUpload(){
    const p = debugProfile ? profiler() : null
    if (pending === 0) {
      showMessage('No hay operaciones para sincronizar.', 'error')
      return
    }
    
    const currentEmpleadoId = localStorage.getItem('empleado_identificacion')
    
    if (!currentEmpleadoId) {
      showMessage('No hay empleado seleccionado. Selecciona un empleado primero.', 'error')
      return
    }

    // Verificar permisos ANTES de empezar cualquier trabajo
    try {
      const perms = await apiClient.getEmpleadoPermissions(currentEmpleadoId)
      const today = getLocalDateString()
      const last = String(perms?.fecha_accion || '')
      const canByDate = !last || last < today
      const canUpload = Boolean(perms?.subir)
      
      if (!canUpload) {
        showMessage('❌ PERMISO DENEGADO: No tienes autorización para subir datos. Contacta al administrador para habilitar el permiso de subida.', 'error')
        return
      }
      
      if (!canByDate) {
        showMessage('❌ FECHA BLOQUEADA: Ya se realizó una subida hoy. La próxima subida estará disponible mañana.', 'error')
        return
      }
      
      if (!(canByDate && canUpload)) {
        showMessage('❌ ACCESO DENEGADO: No cumples con las condiciones para subir datos. Verifica permisos y fecha de última acción.', 'error')
        return
      }
    } catch (e) {
      showMessage('❌ ERROR DE PERMISOS: No se pudo verificar los permisos de subida. Verifica tu conexión y contacta al administrador si el problema persiste.', 'error')
      return
    }
    
    setBusy(true)
    showMessage('Sincronizando datos...', 'info')
    
    // Timeout de seguridad para evitar que se quede colgado
    const timeoutId = setTimeout(() => {
      if (busy) {
        setBusy(false)
        showMessage('❌ TIMEOUT: La sincronización tardó demasiado. Verifica tu conexión e inténtalo de nuevo.', 'error')
      }
    }, 180000) // 3 minutos
    
    try {
      p && p.mark('start')
      const outbox = await offlineDB.readOutbox()
      p && p.mark('readOutbox')
      
      // Obtener las tarjetas del empleado actual para filtrar abonos
      const tarjetasEmpleado = await offlineDB.getTarjetas()
      p && p.mark('getTarjetas')
      const codigosTarjetasEmpleado = new Set(
        tarjetasEmpleado
          .filter(t => t.empleado_identificacion === currentEmpleadoId)
          .map(t => t.codigo)
      )
      
      // Filtrar solo los datos del empleado actualmente seleccionado
      const empleadoData = outbox.filter(item => {
        const itemEmpleadoId = item.empleado_identificacion || item.empleado_id
        
        // Para abonos, verificar que la tarjeta pertenezca al empleado actual
        if (item.type === 'abono:add') {
          return codigosTarjetasEmpleado.has(item.tarjeta_codigo)
        }
        
        // Para otros tipos, usar el empleado_identificacion
        return itemEmpleadoId === currentEmpleadoId
      })
      p && p.mark('filterOutbox')
      
      // Validar que hay datos para sincronizar del empleado actual
      const hasData = empleadoData.some(item => 
        (item.type === 'tarjeta:new' && item.temp_id?.startsWith('tmp-')) ||
        item.type === 'abono:add' ||
        item.type === 'gasto:new' ||
        item.type === 'base:set'
      )
      
      if (!hasData) {
        showMessage('No hay datos válidos para sincronizar del empleado actual.', 'error')
        return
      }

      // Construir payload según /sync
      const idempotencyKey = `sync-${Date.now()}`
      const payload = {
        idempotency_key: idempotencyKey,
        tarjetas_nuevas: [],
        abonos: [],
        gastos: [],
        bases: [],
      }
      
      let syncCount = 0
      
      for (const item of empleadoData) {
        if (item.type === 'tarjeta:new') {
          // Solo sincronizar tarjetas creadas offline con id temporal
          if (!item.temp_id || typeof item.temp_id !== 'string' || !item.temp_id.startsWith('tmp-')) {
            continue
          }
          payload.tarjetas_nuevas.push({
            temp_id: item.temp_id,
            cliente: item.cliente,
            empleado_identificacion: item.empleado_identificacion,
            monto: item.monto,
            cuotas: item.cuotas,
            interes: item.interes,
            numero_ruta: item.numero_ruta,
            observaciones: item.observaciones,
            posicion_anterior: item.posicion_anterior,
            posicion_siguiente: item.posicion_siguiente,
          })
          syncCount++
        } else if (item.type === 'abono:add') {
          // Los abonos ya están filtrados por tarjetas del empleado actual
          payload.abonos.push({
            id_temporal: item.id_temporal,
            tarjeta_codigo: item.tarjeta_codigo,
            monto: item.monto,
            metodo_pago: item.metodo_pago || 'efectivo',
          })
          syncCount++
        } else if (item.type === 'gasto:new') {
          payload.gastos.push({
            empleado_identificacion: item.empleado_identificacion || currentEmpleadoId,
            tipo: item.tipo,
            valor: item.valor,
            observacion: item.observacion,
            fecha: item.fecha,
          })
          syncCount++
        } else if (item.type === 'base:set') {
          payload.bases.push({
            empleado_id: item.empleado_id || item.empleado_identificacion || currentEmpleadoId,
            fecha: item.fecha,
            monto: item.monto,
          })
          syncCount++
        }
      }
      p && p.mark('buildPayload')

      if (syncCount === 0) {
        showMessage('No hay datos válidos para sincronizar.', 'error')
        return
      }

      // Debug: Mostrar datos que se van a sincronizar
      console.log('=== DATOS A SINCRONIZAR ===')
      console.log('Empleado actual:', currentEmpleadoId)
      console.log('Gastos:', payload.gastos)
      console.log('Bases:', payload.bases)
      console.log('Tarjetas:', payload.tarjetas_nuevas.length)
      console.log('Abonos:', payload.abonos.length)

      // Obtener empleado_identificacion (truncado a 20 caracteres)
      const rawEmpleadoId = localStorage.getItem('empleado_identificacion')
      const empleadoId = rawEmpleadoId ? String(rawEmpleadoId).substring(0, 20) : null
      
      if (!empleadoId && (payload.gastos.length > 0 || payload.bases.length > 0)) {
        showMessage('No se encontró empleado_identificacion en la sesión. Debes seleccionar un empleado primero.', 'error')
        return
      }

      // Asegurar que todos los gastos tengan empleado_identificacion
      payload.gastos = payload.gastos.map(gasto => ({
        ...gasto,
        empleado_identificacion: gasto.empleado_identificacion || empleadoId
      }))

      // Asegurar que todas las bases tengan empleado_id
      payload.bases = payload.bases.map(base => ({
        ...base,
        empleado_id: base.empleado_id || empleadoId
      }))
      p && p.mark('normalizePayload')


      const res = await apiClient.sync(payload)
      p && p.mark('apiSync')
      
      // Debug: Mostrar respuesta de sincronización
      console.log('=== RESPUESTA DE SINCRONIZACIÓN ===')
      console.log('Respuesta completa:', res)
      console.log('Gastos creados:', res?.data?.created_gastos)
      console.log('Bases creadas:', res?.data?.created_bases)

      // Manejo explícito de estados/resultados
      if (!res?.success) {
        const status = res?.status
        const type = res?.type
        const baseMsg = res?.message || 'Error de sincronización'
        if (type === 'timeout') {
          showMessage(`❌ SINCRONIZACIÓN FALLIDA (Tiempo de espera) — Etapa: envío al servidor. ${baseMsg}`, 'error')
          return
        }
        if (type === 'network') {
          showMessage(`❌ SINCRONIZACIÓN FALLIDA (Conexión) — Etapa: envío al servidor. ${baseMsg}`, 'error')
          return
        }
        if (type === 'permission') {
          showMessage(`❌ PERMISO DENEGADO — Etapa: validación de permisos. ${baseMsg}`, 'error')
          return
        }
        if (type === 'daily-limit') {
          showMessage(`❌ LÍMITE DIARIO — Etapa: validación de permisos. ${baseMsg}`, 'error')
          return
        }
        if (type === 'multiple-employees') {
          showMessage(`❌ DATOS INCONSISTENTES — Etapa: validación de payload. ${baseMsg}`, 'error')
          return
        }
        if (type === 'bad-request' || status === 400) {
          showMessage(`❌ DATOS INVÁLIDOS — Etapa: validación de payload. ${baseMsg}`, 'error')
          return
        }
        if (type === 'not-found' || status === 404) {
          showMessage(`❌ RECURSO NO ENCONTRADO — Etapa: validación de datos. ${baseMsg}`, 'error')
          return
        }
        if (type === 'validation' || status === 422) {
          showMessage(`❌ ERROR DE VALIDACIÓN — Etapa: validación de payload. ${baseMsg}`, 'error')
          return
        }
        if (type === 'server' || status === 500) {
          showMessage(`❌ ERROR DEL SERVIDOR — Etapa: procesamiento en servidor. ${baseMsg}`, 'error')
          return
        }
        showMessage(`❌ ERROR DE SINCRONIZACIÓN — ${baseMsg}`, 'error')
        return
      }

      // Mapear IDs temporales de tarjetas a códigos reales
      if (res?.data?.created_tarjetas?.length) {
        const tarjetas = await offlineDB.getTarjetas()
        const map = new Map(res.data.created_tarjetas.map(x => [x.temp_id, x.codigo]))
        const updated = tarjetas.map(t => map.has(t.temp_id) ? { ...t, codigo: map.get(t.temp_id) } : t)
        await offlineDB.setTarjetas(updated)
      }
      p && p.mark('mapTempIds')

      // Limpiar outbox tras éxito
      await Promise.all(outbox.map(item => offlineDB.removeOutbox(item.id)))
      p && p.mark('clearOutbox')

      // Marcar fin de jornada: limpiar caches auxiliares
      await offlineDB.resetWorkingMemory()
      localStorage.removeItem('tarjetas_data')
      localStorage.removeItem('tarjetas_stats')
      localStorage.removeItem('tarjetas_last_download')
      p && p.mark('resetCache')

      // Permisos: el backend ajusta estados al finalizar /sync. Evitar llamada extra desde frontend
      p && p.mark('updatePerm')

      // Actualizar UI inmediatamente (panel a 0) antes de mostrar mensaje
      setPending(0)
      setOutboxData({ tarjetas: 0, abonos: 0, gastos: 0, bases: 0 })
      setLocalGastos([])
      setLocalBases([])
      setBusy(false)

      // Calcular resumen desde la respuesta para precisión
      const createdTarjetas = Number(res?.data?.created_tarjetas?.length || 0)
      const createdAbonos = Number(res?.data?.created_abonos?.length || 0)
      const createdGastos = Number(res?.data?.created_gastos || 0)
      const createdBases = Number(res?.data?.created_bases || 0)
      const totalSync = createdTarjetas + createdAbonos + createdGastos + createdBases
      const alreadyProcessed = Boolean(res?.data?.already_processed)
      const successMsg = alreadyProcessed
        ? 'Operación idempotente: ya había sido procesada anteriormente.'
        : `Sincronización completada. Cambios aplicados — Tarjetas: ${createdTarjetas}, Abonos: ${createdAbonos}, Gastos: ${createdGastos}, Bases: ${createdBases}.`

      showMessage(`${successMsg} Total: ${totalSync}.`, 'success')
      localStorage.setItem('flash_message', 'Sincronización completada con éxito. Listo para nueva jornada.')
      p && p.table()
      
      // Mantener mensaje de éxito visible 10s y luego volver a inicio
      try { await refresh() } catch {}
      setTimeout(() => { navigate('/home') }, 10000)
      
    } catch (e) {
      // Errores inesperados fuera del flujo de apiClient.sync
      console.error('Error en sincronización (inesperado):', e)
      showMessage('❌ ERROR INESPERADO — Etapa: cliente. ' + (e?.message || 'Revisa la consola y tu conexión'), 'error')
    } finally {
      clearTimeout(timeoutId)
      setBusy(false)
      refresh()
    }
  }

  async function handleClear(){
    if (pending > 0) {
      showMessage('Hay operaciones pendientes. Sincroniza primero antes de limpiar.', 'error')
      return
    }
    setBusy(true)
    showMessage('Limpiando memoria de trabajo...', 'info')
    try {
      await offlineDB.resetWorkingMemory()
      localStorage.removeItem('tarjetas_data')
      localStorage.removeItem('tarjetas_stats')
      localStorage.removeItem('tarjetas_last_download')
      showMessage('Memoria de trabajo limpiada exitosamente.', 'success')
    } catch (e) {
      showMessage('Error al limpiar memoria: ' + (e?.message || 'Error'), 'error')
    } finally {
      setBusy(false)
      refresh()
    }
  }


  async function deleteGasto(gastoId) {
    try {
      await offlineDB.removeOutbox(gastoId)
      showMessage('Gasto eliminado exitosamente.', 'success')
      refresh()
    } catch (e) {
      showMessage('Error al eliminar gasto: ' + (e?.message || 'Error'), 'error')
    }
  }

  async function updateGasto(gasto) {
    try {
      // Actualizar el gasto en el outbox
      await offlineDB.removeOutbox(gasto.id)
      await offlineDB.queueOperation({
        type: 'gasto:new',
        tipo: gasto.tipo,
        valor: gasto.valor,
        observacion: gasto.observacion,
        fecha: gasto.fecha,
        empleado_identificacion: gasto.empleado_identificacion,
        ts: Date.now()
      })
      
      showMessage('Gasto actualizado exitosamente.', 'success')
      refresh()
    } catch (e) {
      showMessage('Error al actualizar gasto: ' + (e?.message || 'Error'), 'error')
    }
  }

  async function deleteBase(baseId) {
    try {
      await offlineDB.removeOutbox(baseId)
      showMessage('Base eliminada exitosamente.', 'success')
      refresh()
    } catch (e) {
      showMessage('Error al eliminar base: ' + (e?.message || 'Error'), 'error')
    }
  }

  async function updateBase(base) {
    try {
      // Actualizar la base en el outbox
      await offlineDB.removeOutbox(base.id)
      await offlineDB.queueOperation({
        type: 'base:set',
        fecha: base.fecha,
        monto: base.monto,
        empleado_id: base.empleado_id || base.empleado_identificacion,
        ts: Date.now()
      })
      
      showMessage('Base actualizada exitosamente.', 'success')
      refresh()
    } catch (e) {
      showMessage('Error al actualizar base: ' + (e?.message || 'Error'), 'error')
    }
  }

  const hasDataToSync = outboxData.tarjetas > 0 || outboxData.abonos > 0 || outboxData.gastos > 0 || outboxData.bases > 0

  const currentEmpleadoId = localStorage.getItem('empleado_identificacion')

  return (
    <div className="app-shell">
      <header className="app-header"><h1>Sincronizar</h1></header>
      <main>
        {/* Indicador de empleado actual */}
        {currentEmpleadoId && (
          <div className="card" style={{maxWidth:680, background:'#1e3a8a', color:'white'}}>
            <strong>Empleado actual: {localStorage.getItem('empleado_nombre') || currentEmpleadoId}</strong>
            <span style={{color:'#93c5fd', fontSize:14}}>ID: {currentEmpleadoId}</span>
            <span style={{color:'#93c5fd', fontSize:14}}>Solo se sincronizarán los datos de este empleado</span>
          </div>
        )}
        
        {!currentEmpleadoId && (
          <div className="card" style={{maxWidth:680, background:'#7f1d1d', color:'white'}}>
            <strong>⚠️ No hay empleado seleccionado</strong>
            <span style={{color:'#fca5a5', fontSize:14}}>Debes seleccionar un empleado primero para sincronizar datos</span>
          </div>
        )}

        {/* Estado de sincronización */}
        <div className="card" style={{maxWidth:680}}>
          <strong>Estado de sincronización</strong>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginTop:8}}>
            <div>Tarjetas nuevas: <b>{outboxData.tarjetas}</b></div>
            <div>Abonos: <b>{outboxData.abonos}</b></div>
            <div>Gastos: <b>{outboxData.gastos}</b></div>
            <div>Bases: <b>{outboxData.bases}</b></div>
          </div>
          <div style={{marginTop:8, padding:8, background: hasDataToSync ? '#14532d' : '#7f1d1d', borderRadius:4, color:'white'}}>
            {hasDataToSync ? 'Hay datos para sincronizar' : 'No hay datos para sincronizar'}
          </div>
        </div>

        {/* Gastos locales */}
        {localGastos.length > 0 && (
          <div className="card" style={{maxWidth:680, overflow:'hidden'}}>
            <strong>Gastos pendientes</strong>
            {localGastos.map((gasto, idx) => (
              <div key={gasto.id || idx} style={{padding:8, border:'1px solid #223045', borderRadius:4, marginTop:8}}>
                <input 
                  value={gasto.observacion || ''} 
                  onChange={(e)=>setLocalGastos(prev=>prev.map((g,i)=>i===idx?{...g,observacion:e.target.value}:g))} 
                  placeholder="Detalle del gasto" 
                  style={{width:'100%', marginBottom:8}}
                />
                <div style={{display:'flex', gap:4, alignItems:'center'}}>
                  <input 
                    value={gasto.valor} 
                    onChange={(e)=>setLocalGastos(prev=>prev.map((g,i)=>i===idx?{...g,valor:Number(e.target.value)}:g))} 
                    placeholder="Valor" 
                    style={{width:120, marginRight:4}}
                    type="number"
                  />
                  <button onClick={()=>updateGasto(gasto)} style={{color:'green'}} title="Actualizar"><Check size={16}/></button>
                  <button onClick={()=>deleteGasto(gasto.id)} style={{color:'red'}} title="Eliminar"><Trash2 size={16}/></button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Bases locales */}
        {localBases.length > 0 && (
          <div className="card" style={{maxWidth:680, overflow:'hidden'}}>
            <strong>Bases pendientes</strong>
            {localBases.map((base, idx) => (
              <div key={base.id || idx} style={{display:'flex', flexWrap:'wrap', gap:8, padding:8, border:'1px solid #223045', borderRadius:4, marginTop:8, alignItems:'center'}}>
                <input 
                  value={base.fecha} 
                  onChange={(e)=>setLocalBases(prev=>prev.map((b,i)=>i===idx?{...b,fecha:e.target.value}:b))} 
                  type="date" 
                  style={{flex:'1 1 140px', minWidth:140}}
                />
                <input 
                  value={base.monto} 
                  onChange={(e)=>setLocalBases(prev=>prev.map((b,i)=>i===idx?{...b,monto:Number(e.target.value)}:b))} 
                  placeholder="Monto" 
                  style={{flex:'1 1 120px', minWidth:120}}
                  type="number"
                />
                <button onClick={()=>updateBase(base)} style={{color:'green', flex:'0 0 auto'}} title="Actualizar"><Check size={16}/></button>
                <button onClick={()=>deleteBase(base.id)} style={{color:'red', flex:'0 0 auto'}} title="Eliminar"><Trash2 size={16}/></button>
              </div>
            ))}
          </div>
        )}

        {/* Botones de acción */}
        <div className="card" style={{maxWidth:680, display:'grid', gap:8}}>
          {message && (
            <div style={{
              padding:8, 
              background: messageType === 'success' ? '#14532d' : messageType === 'error' ? '#7f1d1d' : '#1e3a8a',
              color: 'white',
              borderRadius: 4,
              fontSize: 14,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8
            }}>
              <span style={{flex: 1}}>{message}</span>
              <button 
                onClick={() => setMessage('')}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'white',
                  cursor: 'pointer',
                  padding: '2px 6px',
                  borderRadius: 3,
                  fontSize: 12
                }}
                title="Cerrar mensaje"
              >
                ✕
              </button>
            </div>
          )}
          <div style={{display:'flex', gap:10, alignItems:'center'}}>
            <button className="primary" onClick={handleUpload} disabled={busy || !hasDataToSync}>
              {busy ? 'Sincronizando...' : 'Sincronizar datos'}
            </button>
            <button onClick={handleClear} disabled={busy || pending > 0}>
              Limpiar memoria
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}


