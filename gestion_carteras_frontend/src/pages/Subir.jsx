import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { offlineDB } from '../offline/db.js'
import { apiClient } from '../api/client.js'
import { Edit, Trash2, Check, X } from 'lucide-react'

function currency(n) {
  try {
    return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(Number(n) || 0)
  } catch {
    return `$${Number(n || 0).toFixed(0)}`
  }
}

function formatHour(ts) {
  if (!ts) return ''
  const date = ts instanceof Date ? ts : new Date(ts)
  if (Number.isNaN(date.getTime())) return ''
  try {
    return date.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export default function SubirPage() {
  const [pending, setPending] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('info') // 'success', 'error', 'info'
  const [outboxData, setOutboxData] = useState({ tarjetas: 0, abonos: 0, gastos: 0, bases: 0 })
  const [localGastos, setLocalGastos] = useState([])
  const [localBases, setLocalBases] = useState([])
  const [preflightModal, setPreflightModal] = useState(null)
  const navigate = useNavigate()
  const debugProfile = true

  function profiler() {
    const t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    const marks = []
    return {
      mark(label) { marks.push({ label, t: (typeof performance !== 'undefined' ? performance.now() : Date.now()) }) },
      table() {
        try {
          let prev = t0
          const rows = marks.map(m => { const d = Math.round(m.t - prev); prev = m.t; return { paso: m.label, ms: d } })
          rows.push({ paso: 'TOTAL', ms: Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0) })
          console.table(rows)
        } catch { }
      }
    }
  }

  async function collectEmpleadoOutboxData(empleadoId, profilerInstance = null) {
    const empId = empleadoId ? String(empleadoId) : ''
    profilerInstance?.mark('readOutbox')
    const outbox = await offlineDB.readOutbox()
    profilerInstance?.mark('getTarjetas')
    const tarjetasEmpleado = await offlineDB.getTarjetas()
    const codigosTarjetasEmpleado = new Set(
      (tarjetasEmpleado || [])
        .filter(t => t && String(t.empleado_identificacion) === empId)
        .map(t => String(t.codigo))
    )
    const shadowData = []
    const empleadoData = (outbox || []).filter(item => {
      if (!item) return false
      const isShadow = item.shadow_only === true || item.type === 'tarjeta:shadow' || item.type === 'shadow:tarjeta'
      if (item.type === 'abono:add') {
        if (item.tarjeta_codigo == null) return false
        return codigosTarjetasEmpleado.has(String(item.tarjeta_codigo))
      }
      const itemEmpleadoId = item.empleado_identificacion || item.empleado_id
      const sameEmpleado = itemEmpleadoId != null && String(itemEmpleadoId) === empId
      if (!sameEmpleado) return false
      if (isShadow) {
        shadowData.push(item)
        return false
      }
      return true
    })
    profilerInstance?.mark('filterOutbox')
    return { empleadoData, outbox, shadowData }
  }

  function hasSyncableData(list = []) {
    return list.some(item =>
      (item?.type === 'tarjeta:new' && typeof item?.temp_id === 'string' && item.temp_id.startsWith('tmp-')) ||
      item?.type === 'abono:add' ||
      item?.type === 'gasto:new' ||
      item?.type === 'base:set'
    )
  }

  function summarizeEmpleadoData(items = [], extraItems = []) {
    const list = Array.isArray(extraItems) && extraItems.length ? [...items, ...extraItems] : items
    const totals = {
      recaudoEfectivo: 0,
      recaudoConsignacion: 0,
      recaudoOtros: 0,
      baseTotal: 0,
      prestamosTotal: 0,
      gastosTotal: 0,
    }
    const counts = { tarjetas: 0, abonos: 0, gastos: 0, bases: 0 }
    for (const item of list) {
      if (!item) continue
      if (item.type === 'abono:add') {
        counts.abonos += 1
        const monto = Number(item.monto) || 0
        const metodo = (item.metodo_pago || 'efectivo').toLowerCase()
        if (metodo === 'consignacion') {
          totals.recaudoConsignacion += monto
        } else if (metodo === 'efectivo') {
          totals.recaudoEfectivo += monto
        } else {
          totals.recaudoOtros += monto
        }
      } else if (item.type === 'gasto:new') {
        counts.gastos += 1
        totals.gastosTotal += Number(item.valor) || 0
      } else if (item.type === 'base:set') {
        counts.bases += 1
        totals.baseTotal += Number(item.monto) || 0
      } else if (
        (item.type === 'tarjeta:new' && typeof item.temp_id === 'string' && item.temp_id.startsWith('tmp-')) ||
        item.type === 'tarjeta:shadow'
      ) {
        counts.tarjetas += 1
        totals.prestamosTotal += Number(item.monto) || 0
      }
    }
    totals.recaudoTotal = totals.recaudoEfectivo + totals.recaudoConsignacion + totals.recaudoOtros
    totals.efectivoEntregar = totals.recaudoEfectivo + totals.recaudoConsignacion + totals.baseTotal - totals.prestamosTotal - totals.gastosTotal
    return { totals, counts }
  }

  function buildDetailLists(items = []) {
    const abonos = []
    items.forEach(item => {
      if (!item) return
      if (item.type === 'abono:add') {
        abonos.push({
          id: String(item.id || item.id_temporal || `${item.tarjeta_codigo || 'tarjeta'}-${item.ts || Date.now()}`),
          tarjeta: item.tarjeta_codigo,
          monto: Number(item.monto) || 0,
          metodo: (item.metodo_pago || 'efectivo').toLowerCase(),
          ts: item.ts || Date.now(),
        })
      }
    })
    abonos.sort((a, b) => (a.ts || 0) - (b.ts || 0))
    return { abonos }
  }

  function buildSignature(items = []) {
    return items
      .map(item => {
        if (!item) return null
        if (item.id) return String(item.id)
        const fallback = `${item.type || 'op'}-${item.ts || '0'}-${item.tarjeta_codigo || item.temp_id || ''}`
        return fallback
      })
      .filter(Boolean)
      .sort()
  }

  function signaturesEqual(a = [], b = []) {
    if (a.length !== b.length) return false
    for (let i = 0; i < a.length; i += 1) {
      if (a[i] !== b[i]) return false
    }
    return true
  }

  async function buildPreflightSummary(empleadoId) {
    const snapshot = await collectEmpleadoOutboxData(empleadoId)
    if (!hasSyncableData(snapshot.empleadoData) && !(snapshot.shadowData?.length)) {
      throw new Error('No hay datos válidos para sincronizar del empleado actual.')
    }
    const { totals, counts } = summarizeEmpleadoData(snapshot.empleadoData, snapshot.shadowData)
    const details = buildDetailLists(snapshot.empleadoData)
    const signature = buildSignature([...(snapshot.empleadoData || []), ...(snapshot.shadowData || [])])
    const empleadoNombre = localStorage.getItem('empleado_nombre') || empleadoId
    return { empleadoId, empleadoNombre, totals, counts, signature, shadowData: snapshot.shadowData || [], details }
  }

  async function refresh() {
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
        (tarjetasEmpleado || [])
          .filter(t => t && String(t.empleado_identificacion) === String(currentEmpleadoId))
          .map(t => String(t.codigo))
      )

      // Filtrar solo los datos del empleado actualmente seleccionado
      const empleadoData = outbox.filter(item => {
        if (!item) return false
        if (item.shadow_only || item.type === 'tarjeta:shadow' || item.type === 'shadow:tarjeta') {
          return false
        }
        if (item.type === 'abono:add') {
          if (item.tarjeta_codigo == null) return false
          return codigosTarjetasEmpleado.has(String(item.tarjeta_codigo))
        }
        const itemEmpleadoId = item.empleado_identificacion || item.empleado_id
        return itemEmpleadoId != null && String(itemEmpleadoId) === String(currentEmpleadoId)
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

  useEffect(() => { refresh() }, [])

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

  async function handleUpload() {
    if (busy) return
    const currentEmpleadoId = localStorage.getItem('empleado_identificacion')

    if (!currentEmpleadoId) {
      showMessage('No hay empleado seleccionado. Selecciona un empleado primero.', 'error')
      return
    }

    setBusy(true)
    try {
      const summary = await buildPreflightSummary(currentEmpleadoId)
      setPreflightModal(summary)
      showMessage('Revisa la liquidación y confirma para iniciar la sincronización.', 'info')
    } catch (e) {
      showMessage(e?.message || 'No fue posible preparar la sincronización.', 'error')
    } finally {
      setBusy(false)
    }
  }

  function cancelPreflight() {
    setPreflightModal(null)
    showMessage('Sincronización cancelada antes de enviarse.', 'info')
  }

  async function confirmPreflight() {
    if (!preflightModal) return
    const snapshot = preflightModal
    setPreflightModal(null)
    await performSync(snapshot)
  }

  async function performSync(preflight) {
    if (!preflight) return
    const currentEmpleadoId = preflight.empleadoId
    const p = debugProfile ? profiler() : null

    setBusy(true)
    showMessage('Sincronizando datos...', 'info')

    const timeoutId = setTimeout(() => {
      if (busy) {
        setBusy(false)
        showMessage('❌ TIMEOUT: La sincronización tardó demasiado. Verifica tu conexión e inténtalo de nuevo.', 'error')
      }
    }, 180000)

    try {
      p && p.mark('start')
      const snapshot = await collectEmpleadoOutboxData(currentEmpleadoId, p)
      const empleadoData = snapshot.empleadoData
      const outbox = snapshot.outbox
      const shadowData = snapshot.shadowData || []
      const currentSignature = buildSignature([...(empleadoData || []), ...shadowData])
      if (!signaturesEqual(currentSignature, preflight.signature)) {
        showMessage('Los datos cambiaron mientras revisabas la liquidación. Genera nuevamente el resumen antes de sincronizar.', 'error')
        return
      }

      if (!hasSyncableData(empleadoData)) {
        if (shadowData.length > 0) {
          showMessage('No hay operaciones pendientes para subir. Los préstamos realizados en línea ya quedaron en el servidor; la liquidación se guardó como referencia.', 'info')
        } else {
          showMessage('No hay datos válidos para sincronizar del empleado actual.', 'error')
        }
        return
      }

      // Verificar permisos justo antes de sincronizar
      try {
        const perms = await apiClient.getEmpleadoPermissions(currentEmpleadoId)
        const canUpload = Boolean(perms?.puede_subir ?? false)
        if (!canUpload) {
          if (!perms?.subir) {
            showMessage('❌ PERMISO DENEGADO: No tienes autorización para subir datos. Contacta al administrador para habilitar el permiso de subida.', 'error')
          } else {
            showMessage('❌ FECHA BLOQUEADA: Ya se realizó una subida hoy. La próxima subida estará disponible mañana.', 'error')
          }
          return
        }
      } catch (e) {
        showMessage('❌ ERROR DE PERMISOS: No se pudo verificar los permisos de subida. Verifica tu conexión y contacta al administrador si el problema persiste.', 'error')
        return
      }

      p && p.mark('verifyPerms')

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

      console.log('=== DATOS A SINCRONIZAR ===')
      console.log('Empleado actual:', currentEmpleadoId)
      console.log('Gastos:', payload.gastos)
      console.log('Bases:', payload.bases)
      console.log('Tarjetas:', payload.tarjetas_nuevas.length)
      console.log('Abonos:', payload.abonos.length)

      const rawEmpleadoId = localStorage.getItem('empleado_identificacion')
      const empleadoId = rawEmpleadoId ? String(rawEmpleadoId).substring(0, 20) : null

      if (!empleadoId && (payload.gastos.length > 0 || payload.bases.length > 0)) {
        showMessage('No se encontró empleado_identificacion en la sesión. Debes seleccionar un empleado primero.', 'error')
        return
      }

      payload.gastos = payload.gastos.map(gasto => ({
        ...gasto,
        empleado_identificacion: gasto.empleado_identificacion || empleadoId
      }))

      payload.bases = payload.bases.map(base => ({
        ...base,
        empleado_id: base.empleado_id || empleadoId
      }))
      p && p.mark('normalizePayload')

      const res = await apiClient.sync(payload)
      p && p.mark('apiSync')

      console.log('=== RESPUESTA DE SINCRONIZACIÓN ===')
      console.log('Respuesta completa:', res)
      console.log('Gastos creados:', res?.data?.created_gastos)
      console.log('Bases creadas:', res?.data?.created_bases)

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

      if (res?.data?.created_tarjetas?.length) {
        const tarjetas = await offlineDB.getTarjetas()
        const map = new Map(res.data.created_tarjetas.map(x => [x.temp_id, x.codigo]))
        const updated = tarjetas.map(t => map.has(t.temp_id) ? { ...t, codigo: map.get(t.temp_id) } : t)
        await offlineDB.setTarjetas(updated)
      }
      p && p.mark('mapTempIds')

      await Promise.all(outbox.map(item => offlineDB.removeOutbox(item.id)))
      p && p.mark('clearOutbox')

      await offlineDB.resetWorkingMemory()
      localStorage.removeItem('tarjetas_data')
      localStorage.removeItem('tarjetas_stats')
      localStorage.removeItem('tarjetas_last_download')
      localStorage.removeItem('jornada_token')
      localStorage.removeItem('jornada_started_at')
      p && p.mark('resetCache')

      p && p.mark('updatePerm')

      setPending(0)
      setOutboxData({ tarjetas: 0, abonos: 0, gastos: 0, bases: 0 })
      setLocalGastos([])
      setLocalBases([])

      // CRITICO: Liberar la UI antes de operaciones de limpieza pesadas que podrían bloquearse
      setBusy(false)

      const createdTarjetas = Number(res?.data?.created_tarjetas?.length || 0)
      const createdAbonos = Number(res?.data?.created_abonos?.length || 0)
      const createdGastos = Number(res?.data?.created_gastos || 0)
      const createdBases = Number(res?.data?.created_bases || 0)
      const totalSync = createdTarjetas + createdAbonos + createdGastos + createdBases
      const alreadyProcessed = Boolean(res?.data?.already_processed)
      const successMsg = alreadyProcessed
        ? 'Operación idempotente: ya había sido procesada anteriormente.'
        : `Sincronización completada. Cambios aplicados — Tarjetas: ${createdTarjetas}, Abonos: ${createdAbonos}, Gastos: ${createdGastos}, Bases: ${createdBases}.`

      const totals = preflight?.totals
      const formulaText = totals
        ? ` Efectivo a entregar: ${currency(totals.efectivoEntregar)} = (Recaudo ${currency(totals.recaudoEfectivo)} efectivo + ${currency(totals.recaudoConsignacion)} consignación${totals.recaudoOtros ? ` + ${currency(totals.recaudoOtros)} otros` : ''}) + Base ${currency(totals.baseTotal)} - Préstamos ${currency(totals.prestamosTotal)} - Gastos ${currency(totals.gastosTotal)}.`
        : ''

      showMessage(`${successMsg} Total: ${totalSync}.${formulaText}`, 'success')
      localStorage.setItem('flash_message', 'Sincronización completada con éxito. Listo para nueva jornada.')
      p && p.table()

      // Limpieza final de DB (Puede tardar, pero la UI ya respondió)
      try {
        await Promise.all(outbox.map(item => offlineDB.removeOutbox(item.id)))
        await offlineDB.resetWorkingMemory()
        localStorage.removeItem('tarjetas_data')
        localStorage.removeItem('tarjetas_stats')
        localStorage.removeItem('tarjetas_last_download')
        localStorage.removeItem('jornada_token')
        localStorage.removeItem('jornada_started_at')
      } catch (cleanupErr) {
        console.warn('Error en limpieza post-sync (no crítico):', cleanupErr)
      }

      setTimeout(() => { navigate('/home') }, 10000)

    } catch (e) {
      setBusy(false) // Asegurar desbloqueo en error
      console.error('Error en sincronización (inesperado):', e)
      showMessage('❌ ERROR INESPERADO — Etapa: cliente. ' + (e?.message || 'Revisa la consola y tu conexión'), 'error')
      refresh() // Solo refrescar si hubo error y NO se borró la DB
    } finally {
      clearTimeout(timeoutId)
      // No llamamos a refresh() incondicionalmente aquí para evitar revivir la DB recién borrada
    }
  }

  async function handleClear() {
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
      localStorage.removeItem('jornada_token')
      localStorage.removeItem('jornada_started_at')
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
          <div className="card" style={{ maxWidth: 680, background: '#1e3a8a', color: 'white' }}>
            <strong>Empleado actual: {localStorage.getItem('empleado_nombre') || currentEmpleadoId}</strong>
            <span style={{ color: '#93c5fd', fontSize: 14 }}>ID: {currentEmpleadoId}</span>
            <span style={{ color: '#93c5fd', fontSize: 14 }}>Solo se sincronizarán los datos de este empleado</span>
          </div>
        )}

        {!currentEmpleadoId && (
          <div className="card" style={{ maxWidth: 680, background: '#7f1d1d', color: 'white' }}>
            <strong>⚠️ No hay empleado seleccionado</strong>
            <span style={{ color: '#fca5a5', fontSize: 14 }}>Debes seleccionar un empleado primero para sincronizar datos</span>
          </div>
        )}

        {/* Estado de sincronización */}
        <div className="card" style={{ maxWidth: 680 }}>
          <strong>Estado de sincronización</strong>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
            <div>Tarjetas nuevas: <b>{outboxData.tarjetas}</b></div>
            <div>Abonos: <b>{outboxData.abonos}</b></div>
            <div>Gastos: <b>{outboxData.gastos}</b></div>
            <div>Bases: <b>{outboxData.bases}</b></div>
          </div>
          <div style={{ marginTop: 8, padding: 8, background: hasDataToSync ? '#14532d' : '#7f1d1d', borderRadius: 4, color: 'white' }}>
            {hasDataToSync ? 'Hay datos para sincronizar' : 'No hay datos para sincronizar'}
          </div>
        </div>

        {/* Gastos locales */}
        {localGastos.length > 0 && (
          <div className="card" style={{ maxWidth: 680, overflow: 'hidden' }}>
            <strong>Gastos pendientes</strong>
            {localGastos.map((gasto, idx) => (
              <div key={gasto.id || idx} style={{ padding: 8, border: '1px solid #223045', borderRadius: 4, marginTop: 8 }}>
                <input
                  value={gasto.observacion || ''}
                  onChange={(e) => setLocalGastos(prev => prev.map((g, i) => i === idx ? { ...g, observacion: e.target.value } : g))}
                  placeholder="Detalle del gasto"
                  style={{ width: '100%', marginBottom: 8 }}
                />
                <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                  <input
                    value={gasto.valor}
                    onChange={(e) => setLocalGastos(prev => prev.map((g, i) => i === idx ? { ...g, valor: Number(e.target.value) } : g))}
                    placeholder="Valor"
                    style={{ width: 120, marginRight: 4 }}
                    type="number"
                  />
                  <button onClick={() => updateGasto(gasto)} style={{ color: 'green' }} title="Actualizar"><Check size={16} /></button>
                  <button onClick={() => deleteGasto(gasto.id)} style={{ color: 'red' }} title="Eliminar"><Trash2 size={16} /></button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Bases locales */}
        {localBases.length > 0 && (
          <div className="card" style={{ maxWidth: 680, overflow: 'hidden' }}>
            <strong>Bases pendientes</strong>
            {localBases.map((base, idx) => (
              <div key={base.id || idx} style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: 8, border: '1px solid #223045', borderRadius: 4, marginTop: 8, alignItems: 'center' }}>
                <input
                  value={base.fecha}
                  onChange={(e) => setLocalBases(prev => prev.map((b, i) => i === idx ? { ...b, fecha: e.target.value } : b))}
                  type="date"
                  style={{ flex: '1 1 140px', minWidth: 140 }}
                />
                <input
                  value={base.monto}
                  onChange={(e) => setLocalBases(prev => prev.map((b, i) => i === idx ? { ...b, monto: Number(e.target.value) } : b))}
                  placeholder="Monto"
                  style={{ flex: '1 1 120px', minWidth: 120 }}
                  type="number"
                />
                <button onClick={() => updateBase(base)} style={{ color: 'green', flex: '0 0 auto' }} title="Actualizar"><Check size={16} /></button>
                <button onClick={() => deleteBase(base.id)} style={{ color: 'red', flex: '0 0 auto' }} title="Eliminar"><Trash2 size={16} /></button>
              </div>
            ))}
          </div>
        )}

        {/* Botones de acción */}
        <div className="card" style={{ maxWidth: 680, display: 'grid', gap: 8 }}>
          {message && (
            <div style={{
              padding: 8,
              background: messageType === 'success' ? '#14532d' : messageType === 'error' ? '#7f1d1d' : '#1e3a8a',
              color: 'white',
              borderRadius: 4,
              fontSize: 14,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8
            }}>
              <span style={{ flex: 1 }}>{message}</span>
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
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="primary" onClick={handleUpload} disabled={busy || !hasDataToSync}>
              {busy ? 'Sincronizando...' : 'Sincronizar datos'}
            </button>
            <button onClick={handleClear} disabled={busy || pending > 0}>
              Limpiar memoria
            </button>
          </div>
        </div>
      </main>
      {preflightModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)', zIndex: 9999, display: 'grid', placeItems: 'center' }} role="dialog" aria-modal="true">
          <div className="card" style={{ width: '94%', maxWidth: 720, maxHeight: '90vh', overflow: 'hidden', background: '#0e1526', border: '1px solid #223045', display: 'flex', flexDirection: 'column' }}>
            {/* Contenido scrolleable */}
            <div style={{ padding: 16, overflowY: 'auto' }}>
              <h2 style={{ marginBottom: 8 }}>Liquidación previa a sincronizar</h2>
              <p style={{ marginBottom: 12, color: 'var(--muted)' }}>
                Confirma que los valores corresponden al efectivo del día antes de enviarlo al servidor.
              </p>
              <div style={{ display: 'grid', gap: 12 }}>
                <div style={{ background: '#111b32', padding: 12, borderRadius: 8 }}>
                  <strong>Recaudo del día</strong>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                    <span>Efectivo</span>
                    <b>{currency(preflightModal.totals.recaudoEfectivo)}</b>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                    <span>Consignación</span>
                    <b>{currency(preflightModal.totals.recaudoConsignacion)}</b>
                  </div>
                  {preflightModal.totals.recaudoOtros > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                      <span>Otros métodos</span>
                      <b>{currency(preflightModal.totals.recaudoOtros)}</b>
                    </div>
                  )}
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, borderTop: '1px solid #1f2a44', paddingTop: 6 }}>
                    <span>Total recaudo</span>
                    <b>{currency(preflightModal.totals.recaudoTotal)}</b>
                  </div>
                </div>
                <div style={{ display: 'grid', gap: 8, background: '#111b32', padding: 12, borderRadius: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Base registrada</span>
                    <b>{currency(preflightModal.totals.baseTotal)}</b>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Préstamos nuevos</span>
                    <b>{currency(preflightModal.totals.prestamosTotal)}</b>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Gastos</span>
                    <b>{currency(preflightModal.totals.gastosTotal)}</b>
                  </div>
                </div>
                <div style={{ background: '#14532d', padding: 12, borderRadius: 8, color: 'white' }}>
                  <strong>Efectivo a entregar</strong>
                  <div style={{ fontSize: 24 }}>{currency(preflightModal.totals.efectivoEntregar)}</div>
                  <small style={{ display: 'block', marginTop: 4, color: '#bbf7d0' }}>
                    Recaudo (efectivo + consignación) + Base - Préstamos - Gastos
                  </small>
                </div>
                <div style={{ display: 'grid', gap: 4, fontSize: 13, color: 'var(--muted)' }}>
                  <span>Tarjetas nuevas: <b>{preflightModal.counts.tarjetas}</b></span>
                  <span>Abonos: <b>{preflightModal.counts.abonos}</b></span>
                  <span>Gastos: <b>{preflightModal.counts.gastos}</b></span>
                  <span>Bases: <b>{preflightModal.counts.bases}</b></span>
                </div>
                {preflightModal.details?.abonos?.length > 0 && (
                  <div style={{ background: '#0b1224', padding: 12, borderRadius: 8, border: '1px solid #1f2a44' }}>
                    <strong>Detalle de abonos ({preflightModal.details.abonos.length})</strong>
                    <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                      {preflightModal.details.abonos.map(item => (
                        <div key={item.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, fontSize: 13, borderBottom: '1px dashed #1f2a44', paddingBottom: 4, alignItems: 'center' }}>
                          <div>
                            <div><b>{currency(item.monto)}</b> — {item.metodo === 'consignacion' ? 'Consignación' : 'Efectivo'}</div>
                            <small style={{ color: 'var(--muted)' }}>Tarjeta: {item.tarjeta || '—'}</small>
                          </div>
                          <div style={{ textAlign: 'right', color: 'var(--muted)', fontSize: 12 }}>
                            {formatHour(item.ts)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
            {/* Footer fijo */}
            <div style={{ position: 'relative', display: 'flex', justifyContent: 'flex-end', gap: 10, padding: 12, borderTop: '1px solid #223045', background: '#0e1526', boxShadow: '0 -10px 24px rgba(0,0,0,.45)' }}>
              <button onClick={cancelPreflight}>Cancelar</button>
              <button className="primary" onClick={confirmPreflight}>Aceptar y sincronizar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


