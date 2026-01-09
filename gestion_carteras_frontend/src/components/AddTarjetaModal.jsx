import React, { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client.js'
import { offlineDB } from '../offline/db.js'
import { computeNextRouteNumber } from '../utils/route.js'
import { getLocalDateString } from '../utils/date.js'
import { getCurrentRoleAndEmpleado } from '../utils/jwt.js'

export default function AddTarjetaModal({ onClose, onCreated, posicionAnterior = null, posicionSiguiente = null }) {
  const [{ empleadoId }] = useState(getCurrentRoleAndEmpleado())
  const [step, setStep] = useState('ident') // ident | form_existing | form_new
  const [online, setOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [connecting, setConnecting] = useState(false)

  const [identificacion, setIdentificacion] = useState('')
  const [cliente, setCliente] = useState(null) // si existe
  const [historial, setHistorial] = useState([])

  const [telefono, setTelefono] = useState('')
  const [direccion, setDireccion] = useState('')
  const [monto, setMonto] = useState('')
  const [interes, setInteres] = useState('20')
  const [cuotas, setCuotas] = useState('30')
  const [modalidadPago, setModalidadPago] = useState('diario')
  const [numeroRuta, setNumeroRuta] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [ponerPrimera, setPonerPrimera] = useState(false)

  useEffect(() => {
    const fn = () => {
      const isOnline = navigator.onLine
      console.log('🔍 AddTarjetaModal: Estado de conexión cambiado', { isOnline, navigatorOnline: navigator.onLine })
      setOnline(isOnline)
    }
    fn() // Establecer estado inicial
    window.addEventListener('online', fn)
    window.addEventListener('offline', fn)
    return () => { window.removeEventListener('online', fn); window.removeEventListener('offline', fn) }
  }, [])

  async function suggestRuta() {
    try {
      console.log('🔍 suggestRuta: Iniciando cálculo de ruta')
      const tarjetas = await offlineDB.getTarjetas()
      console.log('🔍 suggestRuta: Tarjetas obtenidas', tarjetas?.length || 0)
      
      const existing = (tarjetas || []).map(t => (t?.numero_ruta != null ? t.numero_ruta : null)).filter(v => v != null)
      console.log('🔍 suggestRuta: Rutas existentes', existing)
      console.log('🔍 suggestRuta: Contexto', { ponerPrimera, posicionAnterior, posicionSiguiente })
      
      const next = computeNextRouteNumber(existing, ponerPrimera ? null : posicionAnterior, ponerPrimera ? (existing.length ? existing[0] : null) : posicionSiguiente)
      console.log('🔍 suggestRuta: Próxima ruta calculada', next)
      
      setNumeroRuta(String(next))
      console.log('✅ suggestRuta: Ruta establecida', String(next))
    } catch (error) {
      console.error('❌ suggestRuta: Error', error)
      setNumeroRuta('100')
    }
  }

  // Formateo con separadores de miles (es-CO) para el campo monto
  function formatMoneyDisplay(rawStr) {
    const digits = String(rawStr || '').replace(/\D/g, '')
    if (!digits) return ''
    try { return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(Number(digits)) } catch { return digits }
  }

  async function handleCheckIdent() {
    setError('')
    if (!identificacion || !/^[0-9A-Za-z-_.]{3,}$/.test(identificacion)) { setError('Identificación inválida'); return }
    if (!online) {
      // offline: saltar a formulario nuevo
      await suggestRuta()
      setStep('form_new')
      return
    }
    
    setConnecting(true)
    setLoading(true)
    try {
      // Timeout de 10 segundos - si la conexión es muy lenta, tratar como offline
      const TIMEOUT_MS = 10000
      let timeoutId
      const timeoutPromise = new Promise((_, reject) => {
        timeoutId = setTimeout(() => reject(new Error('TIMEOUT')), TIMEOUT_MS)
      })
      
      let cli = null
      try {
        cli = await Promise.race([
          apiClient.getClienteByIdentificacion(identificacion),
          timeoutPromise
        ])
        clearTimeout(timeoutId)
      } catch (e) {
        clearTimeout(timeoutId)
        if (e?.message === 'TIMEOUT') {
          // Conexión muy lenta - tratar como offline
          console.log('⏱️ Timeout buscando cliente, continuando como nuevo')
          await suggestRuta()
          setStep('form_new')
          setLoading(false)
          setConnecting(false)
          return
        }
        // Otro error de red - también tratar como cliente nuevo
        cli = null
      }
      
      if (cli && cli.identificacion) {
        setCliente(cli)
        setTelefono(cli.telefono || '')
        setDireccion(cli.direccion || '')
        await suggestRuta()
        setHistorial([])
        setStep('form_existing')
      } else {
        await suggestRuta()
        setStep('form_new')
      }
    } catch (e) {
      // Error inesperado - ir a cliente nuevo para no bloquear
      console.warn('Error verificando cliente:', e)
      await suggestRuta()
      setStep('form_new')
    } finally {
      setLoading(false)
      setConnecting(false)
    }
  }

  function validateCommon() {
    const m = Number(String(monto).replace(/[^0-9]/g, ''))
    const i = Number(String(interes).replace(/[^0-9.]/g, ''))
    const c = Number(String(cuotas).replace(/[^0-9]/g, ''))
    const r = Number(String(numeroRuta).replace(/[^0-9]/g, ''))
    // reglas ajustadas: monto y cuotas solo deben ser positivos
    if (!Number.isFinite(m) || m <= 0) return 'Monto inválido'
    if (!Number.isFinite(i) || i < 0 || i > 50) return 'Interés entre 0 y 50%'
    if (!Number.isFinite(c) || c <= 0) return 'Cuotas inválidas'
    if (!Number.isFinite(r) || r < 1 || r > 9999) return 'Ruta inválida'
    return null
  }

  async function createOnline(payload, clienteDataSnapshot = null) {
    const res = await apiClient.crearTarjeta(payload)
    // Usar la respuesta del backend (que ya incluye cliente y valores correctos)
    try {
      const tarjetas = await offlineDB.getTarjetas()
      const nombreCli = (cliente?.nombre || clienteNombre || '')
      const apellidoCli = (cliente?.apellido || clienteApellido || '')
      const nueva = {
        ...res,
        // Normalizar por si el backend no incluyó algunos opcionales
        estado: res.estado || 'activas',
        monto: Number(res?.monto ?? payload.monto) || 0,
        interes: Number(res?.interes ?? payload.interes) || 0,
        cuotas: Number(res?.cuotas ?? payload.cuotas) || 0,
          modalidad_pago: res?.modalidad_pago || payload.modalidad_pago || 'diario',
        cliente_identificacion: res?.cliente_identificacion || payload.cliente_identificacion,
        cliente: {
          identificacion: res?.cliente?.identificacion || payload.cliente_identificacion,
          nombre: res?.cliente?.nombre || nombreCli,
          apellido: res?.cliente?.apellido || apellidoCli,
          telefono: res?.cliente?.telefono || telefono || null,
          direccion: res?.cliente?.direccion || direccion || null,
        },
      }
      await offlineDB.setTarjetas([nueva, ...(tarjetas||[])])
    } catch {}
    try {
      await recordShadowPrestamo({
        payload,
        cliente: clienteDataSnapshot || {
          identificacion: payload.cliente_identificacion,
          nombre: cliente?.nombre || clienteNombre || '',
          apellido: cliente?.apellido || clienteApellido || '',
          telefono: telefono || '',
          direccion: direccion || '',
        },
        codigo: res?.codigo,
      })
    } catch {}
    return res
  }

  async function queueOffline(payload, clienteData) {
    try {
      console.log('🔍 queueOffline: Iniciando creación offline', { payload, clienteData })
      
      const tempId = `tmp-${Date.now()}-${Math.random().toString(36).slice(2)}`
      console.log('🔍 queueOffline: tempId generado', tempId)
      
      const operationData = {
        type: 'tarjeta:new',
        temp_id: tempId,
        cliente: clienteData,
        empleado_identificacion: payload.empleado_identificacion,
        monto: payload.monto,
        cuotas: payload.cuotas,
        interes: payload.interes,
        modalidad_pago: payload.modalidad_pago || 'diario',
        numero_ruta: payload.numero_ruta,
        observaciones: payload.observaciones || null,
        posicion_anterior: null,
        posicion_siguiente: null,
      }
      console.log('🔍 queueOffline: Datos de operación', operationData)
      
      await offlineDB.queueOperation(operationData)
      console.log('🔍 queueOffline: Operación encolada exitosamente')
      
      // reflejar en cache local para ver la tarjeta en la lista
      try {
        const tarjetas = await offlineDB.getTarjetas()
        console.log('🔍 queueOffline: Tarjetas existentes obtenidas', tarjetas?.length || 0)
        
        const nueva = {
          codigo: tempId,
          temp_id: tempId, // Para identificar que es temporal
          monto: payload.monto,
          interes: payload.interes,
          cuotas: payload.cuotas,
          modalidad_pago: payload.modalidad_pago || 'diario',
          numero_ruta: payload.numero_ruta,
          estado: 'activas',
          fecha_creacion: getLocalDateString(),
          cliente_identificacion: clienteData.identificacion,
          empleado_identificacion: payload.empleado_identificacion, // ← CRÍTICO: necesario para filtrar abonos
          cliente: { ...clienteData },
        }
        console.log('🔍 queueOffline: Nueva tarjeta para cache', nueva)
        
        await offlineDB.setTarjetas([nueva, ...(tarjetas||[])])
        console.log('🔍 queueOffline: Cache actualizado exitosamente')
      } catch (cacheError) {
        console.error('❌ queueOffline: Error actualizando cache', cacheError)
      }
      
      console.log('✅ queueOffline: Completado exitosamente')
      return { temp_id: tempId }
    } catch (error) {
      console.error('❌ queueOffline: Error general', error)
      throw error
    }
  }

  async function recordShadowPrestamo({ payload, cliente, codigo }) {
    try {
      await offlineDB.queueOperation({
        type: 'tarjeta:shadow',
        shadow_only: true,
        empleado_identificacion: payload.empleado_identificacion,
        tarjeta_codigo: codigo || null,
        monto: payload.monto,
        cuotas: payload.cuotas,
        interes: payload.interes,
        numero_ruta: payload.numero_ruta,
        cliente: cliente ? { ...cliente } : null,
        cliente_identificacion: cliente?.identificacion || payload.cliente_identificacion,
        fecha: getLocalDateString(),
        ts: Date.now(),
      })
    } catch (error) {
      console.warn('recordShadowPrestamo: no se pudo registrar prestamo online en outbox', error)
    }
  }

  async function handleSubmitExisting() {
    setError('')
    const effectiveEmpleado = empleadoId || localStorage.getItem('empleado_identificacion')
    if (!effectiveEmpleado) { setError('No se encontró empleado_identificacion en la sesión. Cierra sesión y vuelve a entrar.'); return }
    const err = validateCommon()
    if (err) { setError(err); return }
    const payload = {
      cliente_identificacion: cliente?.identificacion || identificacion,
      empleado_identificacion: effectiveEmpleado,
      monto: parseInt(String(monto).replace(/[^0-9]/g, ''), 10),
      cuotas: parseInt(String(cuotas), 10),
      interes: parseInt(String(interes), 10),
      modalidad_pago: modalidadPago || 'diario',
      numero_ruta: parseInt(String(numeroRuta), 10),
      observaciones,
      posicion_anterior: ponerPrimera ? null : (posicionAnterior != null ? Number(posicionAnterior) : null),
      posicion_siguiente: ponerPrimera ? (Number.isFinite(parseInt(String(numeroRuta),10)) ? parseInt(String(numeroRuta),10) : (posicionSiguiente != null ? Number(posicionSiguiente) : null)) : (posicionSiguiente != null ? Number(posicionSiguiente) : null),
    }
    setLoading(true)
    try {
      if (online) {
        // Actualizar datos del cliente existente antes de crear la tarjeta
        try {
          const ident = cliente?.identificacion || identificacion
          if (ident) {
            await apiClient.updateCliente(ident, {
              nombre: cliente?.nombre || undefined,
              apellido: cliente?.apellido || undefined,
              telefono: telefono || undefined,
              direccion: direccion || undefined,
              observaciones: null,
            })
          }
        } catch {}
        await createOnline(payload, {
          identificacion: cliente?.identificacion || identificacion,
          nombre: cliente?.nombre || '',
          apellido: cliente?.apellido || '',
          telefono,
          direccion,
        })
      } else {
        await queueOffline(payload, { identificacion: cliente.identificacion, nombre: cliente.nombre, apellido: cliente.apellido, telefono, direccion })
      }
      onCreated?.()
      onClose?.()
    } catch (e) {
      setError(e?.message || 'Error al crear tarjeta')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmitNew() {
    try {
      console.log('🔍 handleSubmitNew: Iniciando creación de tarjeta nueva')
      setError('')
      
      if (!identificacion || !clienteNombre || !clienteApellido) { 
        setError('Nombre, apellido e identificación son obligatorios'); 
        return 
      }
      
      const effectiveEmpleado = empleadoId || localStorage.getItem('empleado_identificacion')
      if (!effectiveEmpleado) { 
        setError('No se encontró empleado_identificacion en la sesión. Cierra sesión y vuelve a entrar.'); 
        return 
      }
      
      const err = validateCommon()
      if (err) { 
        setError(err); 
        return 
      }
      
      const clienteData = { identificacion, nombre: clienteNombre, apellido: clienteApellido, telefono, direccion }
      const payload = {
        cliente_identificacion: identificacion,
        empleado_identificacion: effectiveEmpleado,
        monto: parseInt(String(monto).replace(/[^0-9]/g, ''), 10),
        cuotas: parseInt(String(cuotas), 10),
        interes: parseInt(String(interes), 10),
        modalidad_pago: modalidadPago || 'diario',
        numero_ruta: parseInt(String(numeroRuta), 10),
        observaciones,
        posicion_anterior: ponerPrimera ? null : (posicionAnterior != null ? Number(posicionAnterior) : null),
        posicion_siguiente: ponerPrimera ? (Number.isFinite(parseInt(String(numeroRuta),10)) ? parseInt(String(numeroRuta),10) : (posicionSiguiente != null ? Number(posicionSiguiente) : null)) : (posicionSiguiente != null ? Number(posicionSiguiente) : null),
      }
      
      console.log('🔍 handleSubmitNew: Datos validados', { clienteData, payload, online, navigatorOnline: navigator.onLine })
      
      setLoading(true)
      
      // Verificación adicional de estado online
      const isActuallyOnline = navigator.onLine && online
      console.log('🔍 handleSubmitNew: Verificación de estado', { online, navigatorOnline: navigator.onLine, isActuallyOnline })
      
      // Si no hay conexión real, forzar modo offline
      if (!isActuallyOnline) {
        console.log('🔍 handleSubmitNew: Sin conexión detectada, forzando modo offline')
        await queueOffline(payload, clienteData)
      } else {
        // Intentar modo online, pero si falla, cambiar a offline
        try {
          console.log('🔍 handleSubmitNew: Modo online - intentando crear cliente')
          // crear cliente si no existe
          const existing = await apiClient.getClienteByIdentificacion(identificacion).catch((err) => {
            console.log('🔍 handleSubmitNew: Error obteniendo cliente existente', err)
            return null
          })
          console.log('🔍 handleSubmitNew: Cliente existente', existing)
          if (!existing || !existing.identificacion) {
            console.log('🔍 handleSubmitNew: Creando nuevo cliente')
            await apiClient.createCliente({ identificacion, nombre: clienteNombre, apellido: clienteApellido, telefono, direccion, observaciones: null })
          } else {
            console.log('🔍 handleSubmitNew: Cliente existe, actualizando datos')
            await apiClient.updateCliente(identificacion, { nombre: clienteNombre, apellido: clienteApellido, telefono, direccion, observaciones: null })
          }
          await createOnline(payload, clienteData)
        } catch (error) {
          console.log('🔍 handleSubmitNew: Error en modo online, cambiando a offline', error)
          await queueOffline(payload, clienteData)
        }
      }
      
      console.log('✅ handleSubmitNew: Tarjeta creada exitosamente')
      onCreated?.()
      onClose?.()
    } catch (e) {
      console.error('❌ handleSubmitNew: Error', e)
      setError(e?.message || 'Error al crear tarjeta')
    } finally {
      setLoading(false)
    }
  }

  const [clienteNombre, setClienteNombre] = useState('')
  const [clienteApellido, setClienteApellido] = useState('')

  return (
    <div style={{position:'fixed', inset:0, background:'rgba(0,0,0,.5)', display:'grid', placeItems:'center', zIndex:9999, touchAction:'pan-y'}} onClick={onClose}>
      <div className="card" style={{maxWidth:600, width:'92%', maxHeight:'80vh', overflowY:'auto', overflowX:'hidden', background:'#0e1526'}} onClick={(e)=>e.stopPropagation()}>
        <strong>Agregar tarjeta</strong>
        {step === 'ident' && (
          <div style={{display:'grid', gap:10}}>
            <label>Identificación
              <input inputMode="numeric" value={identificacion} maxLength={20} onChange={(e)=>setIdentificacion(e.target.value.replace(/[^0-9A-Za-z-]/g, ''))} onFocus={(e) => e.target.select()} placeholder="Cédula/NIT"/>
            </label>
            <label style={{display:'flex', alignItems:'center', gap:8}}>
              <input type="checkbox" checked={ponerPrimera} onChange={(e)=>setPonerPrimera(e.target.checked)} />
              <span>Poner de primera</span>
            </label>
            {error && <div className="error">{error}</div>}
            {connecting && (
              <div style={{background:'#1e3a8a', border:'1px solid #3b82f6', color:'#93c5fd', borderRadius:12, padding:'12px 16px', fontSize:14, textAlign:'center'}}>
                <div style={{display:'flex', alignItems:'center', justifyContent:'center', gap:8}}>
                  <div style={{width:16, height:16, border:'2px solid #93c5fd', borderTop:'2px solid transparent', borderRadius:'50%', animation:'spin 1s linear infinite'}}></div>
                  <span>Verificando conexión y buscando cliente...</span>
                </div>
                <div style={{marginTop:8, fontSize:12, opacity:0.8}}>
                  Si no hay conexión, se creará como cliente nuevo
                </div>
              </div>
            )}
            <div style={{display:'flex', gap:10, justifyContent:'center'}}>
              <button className="primary" disabled={loading} onClick={handleCheckIdent}>{online ? 'Buscar' : 'Continuar sin conexión'}</button>
              <button onClick={onClose}>Cancelar</button>
            </div>
          </div>
        )}
        {step === 'form_existing' && (
          <div style={{display:'grid', gap:8, width:'100%', boxSizing:'border-box'}}>
            <div className="neon-sub">Cliente: {cliente?.nombre} {cliente?.apellido}</div>
            <div className="neon-sub">ID: {cliente?.identificacion || identificacion}</div>
            <label style={{width:'100%'}}>Teléfono<input inputMode="tel" value={telefono} maxLength={20} onChange={(e)=>setTelefono(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="Teléfono" style={{width:'100%', boxSizing:'border-box'}}/></label>
            <label style={{width:'100%'}}>Dirección<input value={direccion} maxLength={200} onChange={(e)=>setDireccion(e.target.value)} onFocus={(e) => e.target.select()} placeholder="Dirección" style={{width:'100%', boxSizing:'border-box'}}/></label>
            {/* Fila: Monto + Modalidad */}
            <div style={{display:'flex', gap:8, width:'100%', boxSizing:'border-box'}}>
              <label style={{flex:'1 1 auto', minWidth:0}}>Monto<input inputMode="numeric" value={formatMoneyDisplay(monto)} onChange={(e)=>setMonto(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="Ej: 500000" style={{width:'100%', boxSizing:'border-box'}}/></label>
              <label style={{flex:'0 0 100px'}}>Modalidad
                <select value={modalidadPago} onChange={(e)=>setModalidadPago(e.target.value)} style={{width:'100%', boxSizing:'border-box'}}>
                  <option value="diario">diario</option>
                  <option value="semanal">semanal</option>
                  <option value="quincenal">quincenal</option>
                  <option value="mensual">mensual</option>
                </select>
              </label>
            </div>
            {/* Fila: Interés + Cuotas + Ruta (campos pequeños) */}
            <div style={{display:'flex', gap:8, width:'100%', boxSizing:'border-box'}}>
              <label style={{flex:'0 0 70px'}}>Interés %<input inputMode="numeric" type="number" min={0} max={50} step={1} value={interes} onChange={(e)=>setInteres(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="20" style={{width:'100%', boxSizing:'border-box'}}/></label>
              <label style={{flex:'0 0 70px'}}>Cuotas<input inputMode="numeric" type="number" min={1} step={1} value={cuotas} onChange={(e)=>setCuotas(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="30" style={{width:'100%', boxSizing:'border-box'}}/></label>
              <label style={{flex:'0 0 70px'}}>Ruta<input inputMode="numeric" value={numeroRuta} onChange={(e)=>setNumeroRuta(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="100" style={{width:'100%', boxSizing:'border-box'}}/></label>
            </div>
            <label style={{width:'100%'}}>Observaciones<input value={observaciones} maxLength={500} onChange={(e)=>setObservaciones(e.target.value)} onFocus={(e) => e.target.select()} placeholder="Opcional" style={{width:'100%', boxSizing:'border-box'}}/></label>
            {error && <div className="error">{error}</div>}
            <div style={{display:'flex', gap:8, justifyContent:'center', width:'100%'}}>
              <button onClick={onClose}>Cancelar</button>
              <button className="primary" disabled={loading} onClick={handleSubmitExisting}>Crear tarjeta</button>
            </div>
            <div style={{display:'flex', justifyContent:'center', width:'100%'}}>
              <button
                className="neon-btn"
                style={{width:'96%', display:'flex', justifyContent:'center', alignItems:'center', textAlign:'center'}}
                onClick={()=>{
                  const ident = cliente?.identificacion || identificacion
                  if (!ident) return
                  const base = window.location.origin
                  const token = localStorage.getItem('access_token')
                  const url = token
                    ? `${base}/datacredito/${encodeURIComponent(ident)}?token=${encodeURIComponent(token)}`
                    : `${base}/datacredito/${encodeURIComponent(ident)}`
                  // Forzar navegación en la misma pestaña para evitar bloqueos de pop-up
                  window.location.href = url
                }}
              >
                Historial crediticio
              </button>
            </div>
          </div>
        )}
        {step === 'form_new' && (
          <div style={{display:'grid', gap:8, width:'100%', boxSizing:'border-box'}}>
            <div className="neon-sub">Cliente nuevo</div>
            <div className="neon-sub">ID: {identificacion}</div>
            <label style={{width:'100%'}}>Nombre<input value={clienteNombre} maxLength={40} onChange={(e)=>setClienteNombre(e.target.value)} onFocus={(e) => e.target.select()} placeholder="Nombre" style={{width:'100%', boxSizing:'border-box'}}/></label>
            <label style={{width:'100%'}}>Apellido<input value={clienteApellido} maxLength={40} onChange={(e)=>setClienteApellido(e.target.value)} onFocus={(e) => e.target.select()} placeholder="Apellido" style={{width:'100%', boxSizing:'border-box'}}/></label>
            <label style={{width:'100%'}}>Teléfono<input inputMode="tel" value={telefono} maxLength={20} onChange={(e)=>setTelefono(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="Teléfono" style={{width:'100%', boxSizing:'border-box'}}/></label>
            <label style={{width:'100%'}}>Dirección<input value={direccion} maxLength={200} onChange={(e)=>setDireccion(e.target.value)} onFocus={(e) => e.target.select()} placeholder="Dirección" style={{width:'100%', boxSizing:'border-box'}}/></label>
            {/* Fila: Monto + Modalidad */}
            <div style={{display:'flex', gap:8, width:'100%', boxSizing:'border-box'}}>
              <label style={{flex:'1 1 auto', minWidth:0}}>Monto<input inputMode="numeric" value={formatMoneyDisplay(monto)} onChange={(e)=>setMonto(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="Ej: 500000" style={{width:'100%', boxSizing:'border-box'}}/></label>
              <label style={{flex:'0 0 100px'}}>Modalidad
                <select value={modalidadPago} onChange={(e)=>setModalidadPago(e.target.value)} style={{width:'100%', boxSizing:'border-box'}}>
                  <option value="diario">diario</option>
                  <option value="semanal">semanal</option>
                  <option value="quincenal">quincenal</option>
                  <option value="mensual">mensual</option>
                </select>
              </label>
            </div>
            {/* Fila: Interés + Cuotas + Ruta (campos pequeños) */}
            <div style={{display:'flex', gap:8, width:'100%', boxSizing:'border-box'}}>
              <label style={{flex:'0 0 70px'}}>Interés %<input inputMode="numeric" type="number" min={0} max={50} step={1} value={interes} onChange={(e)=>setInteres(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="20" style={{width:'100%', boxSizing:'border-box'}}/></label>
              <label style={{flex:'0 0 70px'}}>Cuotas<input inputMode="numeric" type="number" min={1} step={1} value={cuotas} onChange={(e)=>setCuotas(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="30" style={{width:'100%', boxSizing:'border-box'}}/></label>
              <label style={{flex:'0 0 70px'}}>Ruta<input inputMode="numeric" value={numeroRuta} onChange={(e)=>setNumeroRuta(e.target.value.replace(/\D/g, ''))} onFocus={(e) => e.target.select()} placeholder="100" style={{width:'100%', boxSizing:'border-box'}}/></label>
            </div>
            <label style={{width:'100%'}}>Observaciones<input value={observaciones} maxLength={500} onChange={(e)=>setObservaciones(e.target.value)} onFocus={(e) => e.target.select()} placeholder="Opcional" style={{width:'100%', boxSizing:'border-box'}}/></label>
            {error && <div className="error">{error}</div>}
            <div style={{display:'flex', gap:8, justifyContent:'center', width:'100%'}}>
              <button onClick={onClose}>Cancelar</button>
              <button className="primary" disabled={loading} onClick={handleSubmitNew}>Crear tarjeta</button>
            </div>
            <div style={{display:'flex', justifyContent:'center', width:'100%'}}>
              <button
                className="neon-btn"
                style={{width:'96%', display:'flex', justifyContent:'center', alignItems:'center', textAlign:'center'}}
                onClick={()=>{
                  const ident = identificacion
                  if (!ident) return
                  const base = window.location.origin
                  const token = localStorage.getItem('access_token')
                  const url = token
                    ? `${base}/datacredito/${encodeURIComponent(ident)}?token=${encodeURIComponent(token)}`
                    : `${base}/datacredito/${encodeURIComponent(ident)}`
                  window.location.href = url
                }}
              >
                Historial crediticio
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}


