import React, { useMemo, useState, useEffect, useRef } from 'react'
import { tarjetasStore } from '../state/store.js'
import { offlineDB } from '../offline/db.js'
import { formatDateYYYYMMDD, getLocalDateString, parseISODateToLocal } from '../utils/date.js'
import { computeDerived } from '../utils/derive.js'
import { useNavigate, Outlet, useLocation } from 'react-router-dom'
import { Check, RotateCw, X, Plus } from 'lucide-react'
import AddTarjetaModal from '../components/AddTarjetaModal.jsx'

function currency(n) { try { return new Intl.NumberFormat('es-CO', { style:'currency', currency:'COP', maximumFractionDigits:0 }).format(n||0) } catch { return `$${Number(n||0).toFixed(0)}` } }
function formatMoney(n){ try { return new Intl.NumberFormat('es-CO', { style:'currency', currency:'COP', maximumFractionDigits:0 }).format(n||0) } catch { return `$${Number(n||0).toFixed(0)}` } }
function getCurrentJornada(){
  const token = (typeof localStorage !== 'undefined' && localStorage.getItem('jornada_token')) || ''
  const startedRaw = (typeof localStorage !== 'undefined' && localStorage.getItem('jornada_started_at')) || '0'
  const startedAt = Number(startedRaw)
  return { token, startedAt: Number.isFinite(startedAt) ? startedAt : 0 }
}

export default function TarjetasPage() {
  const [query, setQuery] = useState('')
  const [stats, setStats] = useState(tarjetasStore.getStats())
  const [tarjetas, setTarjetas] = useState(tarjetasStore.getTarjetas())
  const [abonadosHoyMap, setAbonadosHoyMap] = useState({})
  const [abonosPorTarjeta, setAbonosPorTarjeta] = useState({})
  const [showAdd, setShowAdd] = useState(false)
  const [addCtx, setAddCtx] = useState({ posicionAnterior: null, posicionSiguiente: null })
  const [showRecaudos, setShowRecaudos] = useState(false)
  const [scrollToCodigo, setScrollToCodigo] = useState(() => sessionStorage.getItem('last_tarjeta_codigo') || '')
  const location = useLocation()
  const searchInputRef = useRef(null)
  const searchHistoryTokenRef = useRef(null)
  
  // Detectar si hay una ruta hija activa (detalle o abonos)
  const hasChildRoute = location.pathname !== '/tarjetas'

  useEffect(() => {
    async function refreshData() {
      const { token: jornadaToken, startedAt: jornadaInicio } = getCurrentJornada()
      const isCurrentOp = (op) => {
        if (!op) return false
        if (op.session_id && jornadaToken) return op.session_id === jornadaToken
        if (jornadaInicio) return Number(op.ts || 0) >= jornadaInicio
        return true
      }
      const isCurrentAbono = (a) => {
        if (!a) return false
        if (a.session_id && jornadaToken) return a.session_id === jornadaToken
        if (jornadaInicio) return Number(a.ts || 0) >= jornadaInicio
        return true
      }

      const [s, t, outOps] = await Promise.all([
        offlineDB.getStats(),
        offlineDB.getTarjetas(),
        offlineDB.readOutbox().catch(()=>[]),
      ])
      // stats se recalculará abajo con abonos del día para actualización en vivo
      setTarjetas(t.length ? t : tarjetasStore.getTarjetas())
      
      // Obtener abonos de todas las tarjetas
      const abonosMap = {}
      for (const tarjeta of (t.length ? t : tarjetasStore.getTarjetas())) {
        try {
          const abonos = await offlineDB.getAbonos(tarjeta.codigo)
          abonosMap[tarjeta.codigo] = abonos || []
        } catch {
          abonosMap[tarjeta.codigo] = []
        }
      }
      setAbonosPorTarjeta(abonosMap)
      
      // Construir mapa de tarjetas con abonos de la jornada actual (incluye outbox y abonos guardados)
      const map = {}
      let totalMontoHoy = 0
      let totalCountHoy = 0
      try {
        // Marcar por outbox (acciones locales de la jornada) y sumar montos
        const opsSesion = outOps.filter(isCurrentOp)
        const abonosOutboxSesion = opsSesion.filter(op => op?.op === 'abono')
        const abonoOutboxIds = new Set(
          abonosOutboxSesion.map(op => String(op?.id || `${op?.tarjeta_codigo || ''}-${op?.ts || 0}`))
        )
        opsSesion.sort((a,b)=>a.ts-b.ts).forEach(op => {
          if (op.op === 'abono') {
            map[op.tarjeta_codigo] = true
            totalMontoHoy += Number(op.monto || 0)
            totalCountHoy += 1
          }
          if (op.op === 'reset_abono') {
            map[op.tarjeta_codigo] = false
            // Restar el monto del abono que se resetea
            totalMontoHoy -= Number(op.monto || 0)
            totalCountHoy -= 1
          }
        })
        // Marcar por abonos presentes en IndexedDB y computar totales en vivo
        const perTar = await Promise.all((t || []).map(async (tar) => {
          try {
            const ab = await offlineDB.getAbonos(tar.codigo)
            const { totHoy, countHoy } = (ab||[]).reduce((acc,a)=>{
              if (!isCurrentAbono(a)) return acc
              const entryId = a && (a.id || a.outbox_id)
              if (entryId && abonoOutboxIds.has(String(entryId))) {
                return acc
              }
              acc.totHoy += Number(a?.monto||0)
              acc.countHoy += 1
              return acc
            }, { totHoy: 0, countHoy: 0 })
            return { codigo: tar.codigo, totHoy, countHoy }
          } catch {
            return { codigo: tar.codigo, totHoy: 0, countHoy: 0 }
          }
        }))
        perTar.forEach(({ codigo, totHoy, countHoy }) => {
          if (totHoy > 0) map[codigo] = true
          totalMontoHoy += Number(totHoy||0)
          totalCountHoy += Number(countHoy||0)
        })
      } catch {}
      setAbonadosHoyMap(map)
      setStats({ monto: totalMontoHoy, abonos: totalCountHoy })
    }
    refreshData()
    // Escuchar actualizaciones del outbox
    const handler = () => refreshData()
    window.addEventListener('outbox-updated', handler)
    // Solo hacer scroll inicial si no hay código de tarjeta específica ni posición guardada
    const savedY = Number(sessionStorage.getItem('tarjetas_last_scroll') || '0')
    if (!scrollToCodigo && !savedY) {
      window.scrollTo({ top: 0, behavior: 'instant' })
    }
    return () => window.removeEventListener('outbox-updated', handler)
  }, [])

  // Bloquear scroll del fondo cuando el overlay de Recaudos está abierto
  useEffect(() => {
    const prev = document.body.style.overflow
    if (showRecaudos) {
      document.body.style.overflow = 'hidden'
    }
    return () => { document.body.style.overflow = prev }
  }, [showRecaudos])

  const filtradas = useMemo(() => {
    const q = query.trim().toLowerCase()
    // Ordenar por numero_ruta ascendente; los que no tengan ruta al final
    const ordered = [...tarjetas].sort((a,b)=>{
      const ra = a?.numero_ruta != null ? Number(a.numero_ruta) : Number.POSITIVE_INFINITY
      const rb = b?.numero_ruta != null ? Number(b.numero_ruta) : Number.POSITIVE_INFINITY
      return (ra - rb)
    })
    if (!q) return ordered
    return ordered.filter(t => {
      const nombre = ((t?.cliente?.nombre || '') + ' ' + (t?.cliente?.apellido || '')).trim()
      return nombre.toLowerCase().includes(q)
    })
  }, [query, tarjetas])

  // Permitir que el botón/gesto "Atrás" limpie la búsqueda antes de salir de la lista
  useEffect(() => {
    if (typeof window === 'undefined') return
    const hasQuery = query.trim().length > 0
    if (hasQuery) {
      if (!searchHistoryTokenRef.current) {
        const token = `search-${Date.now()}-${Math.random().toString(36).slice(2)}`
        searchHistoryTokenRef.current = token
        const newState = { ...(window.history.state || {}), searchToken: token }
        window.history.pushState(newState, '', window.location.href)
      }
    } else if (searchHistoryTokenRef.current) {
      if (window.history.state && window.history.state.searchToken === searchHistoryTokenRef.current) {
        const nextState = { ...window.history.state }
        delete nextState.searchToken
        window.history.replaceState(nextState, '', window.location.href)
      }
      searchHistoryTokenRef.current = null
    }
  }, [query])

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const handlePopState = (event) => {
      if (!searchHistoryTokenRef.current) return
      const stateToken = event?.state?.searchToken || null
      if (stateToken === searchHistoryTokenRef.current) return
      searchHistoryTokenRef.current = null
      setQuery('')
      window.setTimeout(() => {
        try { searchInputRef.current?.blur() } catch {}
      }, 0)
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  // Efecto separado para restaurar scroll cuando las tarjetas estén renderizadas
  useEffect(() => {
    if (filtradas.length > 0) {
      const timer = setTimeout(() => {
        try {
          // 1) Restaurar por número de ruta (aproximación robusta ante inserciones)
          const rutaRaw = sessionStorage.getItem('restore_ruta')
          if (rutaRaw != null && rutaRaw !== '') {
            const ruta = Number(rutaRaw)
            if (Number.isFinite(ruta)) {
              const up = filtradas.find(t => Number(t?.numero_ruta) >= ruta)
              const down = [...filtradas].reverse().find(t => Number(t?.numero_ruta) <= ruta)
              const target = up || down
              if (target) {
                const el = document.querySelector(`[data-tarjeta-id="${target.codigo}"]`)
                if (el) {
                  const header = document.querySelector('.app-header')
                  const headerH = header?.getBoundingClientRect()?.height || 0
                  const rect = el.getBoundingClientRect()
                  const baseY = (window.scrollY || window.pageYOffset || 0)
                  const targetY = Math.max(0, baseY + rect.top - headerH - 6)
                  window.scrollTo({ top: targetY, behavior: 'instant' })
                  return
                }
              }
            }
          }
          // 2) Por código específico (fallback)
          const code2 = sessionStorage.getItem('last_tarjeta_codigo') || scrollToCodigo
          if (code2) {
            const el2 = document.querySelector(`[data-tarjeta-id="${code2}"]`)
            if (el2) { el2.scrollIntoView({ behavior: 'instant', block: 'start' }); return }
          }
          // 3) Fallback: scroll absoluto guardado
          const saved = Number(sessionStorage.getItem('tarjetas_last_scroll') || '0')
          if (saved) { window.scrollTo({ top: saved, behavior: 'instant' }); return }
        } finally {
          sessionStorage.removeItem('restore_ruta')
          sessionStorage.removeItem('last_tarjeta_codigo')
          sessionStorage.removeItem('tarjetas_last_scroll')
          setScrollToCodigo('')
        }
      }, 0)
      return () => clearTimeout(timer)
    }
  }, [filtradas.length, scrollToCodigo])

function RecaudosOverlay({ tarjetas, abonosPorTarjeta, onClose }){
  const today = formatDateYYYYMMDD()
  const [abonosHoyPorTarjeta, setAbonosHoyPorTarjeta] = useState({})
  const [totalHoy, setTotalHoy] = useState(0)
  const [noAbonan, setNoAbonan] = useState([])
  const [siAbonan, setSiAbonan] = useState([])
  const [tarjetasNuevas, setTarjetasNuevas] = useState([])
  const [canceladasHoy, setCanceladasHoy] = useState([])

  useEffect(()=>{
    let cancelled = false
    ;(async()=>{
      try {
        // Obtener outbox para verificar operaciones locales pendientes
        const outOps = await offlineDB.readOutbox().catch(()=>[])
        
        // --- 1. TARJETAS NUEVAS ---
        const tarjetasNuevasOffline = outOps.filter(op => 
          op && op.type === 'tarjeta:new' && 
          op.ts && formatDateYYYYMMDD(new Date(op.ts)) === today
        ).map(op => ({
          codigo: op.temp_id || 'temp',
          cliente: op.cliente || {},
          monto: op.monto || 0
        }))
        
        const tarjetasNuevasOnline = (tarjetas || []).filter(t => {
          const fechaCreacion = t?.fecha_creacion || t?.created_at
          if (!fechaCreacion) return false
          const fecha = fechaCreacion instanceof Date ? 
            formatDateYYYYMMDD(fechaCreacion) : 
            formatDateYYYYMMDD(parseISODateToLocal(String(fechaCreacion)))
          return fecha === today
        }).map(t => ({
          codigo: t.codigo,
          cliente: t.cliente || {},
          monto: t.monto || 0
        }))
        
        const tarjetasNuevasHoy = [...tarjetasNuevasOnline, ...tarjetasNuevasOffline]
          .filter((t, index, arr) => arr.findIndex(other => other.codigo === t.codigo) === index)

        // --- 2. ABONOS DEL DÍA (Online + Offline/Outbox) ---
        // Abonos en outbox hechos hoy
        const abonosOutboxHoy = outOps.filter(op => 
          op && op.op === 'abono' && 
          op.ts && formatDateYYYYMMDD(new Date(op.ts)) === today
        )
        // IDs de abonos en outbox para evitar duplicar si ya se sincronizaron parcialmente
        const abonoOutboxIds = new Set(
          abonosOutboxHoy.map(op => String(op?.id || `${op?.tarjeta_codigo || ''}-${op?.ts || 0}`))
        )
        
        // Calcular totales por tarjeta
        const entries = (tarjetas||[]).map(t => {
          const list = abonosPorTarjeta[t.codigo] || []
          const seenIds = new Set()
          
          // Sumar abonos de la DB que sean de hoy
          const sumDB = list.reduce((s,a)=>{
            const d = a?.fecha ? parseISODateToLocal(String(a.fecha)) : (a?.ts ? new Date(a.ts): null)
            if (d && formatDateYYYYMMDD(d) === today) {
              const entryId = a && (a.id || a.outbox_id)
              if (entryId) {
                seenIds.add(String(entryId))
                // Si este abono ya está en outbox (porque se bajó pero sigue pendiente de confirmación o algo así),
                // o si la lógica de outbox lo cubre, hay que tener cuidado.
                // Simplificación: si está en DB y es de hoy, lo sumamos. 
                // PERO si también está en outbox, la lógica de abajo lo sumaría de nuevo?
                // `abonosOutboxHoy` son operaciones pendientes. 
                // Si ya se sincronizó, debería desaparecer de outbox.
                // Si está en outbox, NO debería estar en DB todavía (a menos que sea un update?).
                // Asumimos que si está en DB es "confirmado" o "sincronizado".
                // EXCEPCIÓN: Si acabamos de agregar a DB localmente (optimistic UI) y TAMBIÉN a outbox.
                // `handlePagarCuota` hace ambas cosas: `offlineDB.queueOperation` Y `offlineDB.setAbonos`.
                // Por tanto, debemos evitar duplicados.
                if (abonoOutboxIds.has(String(entryId))) {
                   // Ya lo contaremos desde el outbox o viceversa.
                   // Mejor contarlo aquí (DB) y excluirlo de la suma de outbox si ya está "visto".
                   return s + Number(a?.monto||0)
                }
              }
              return s + Number(a?.monto||0)
            }
            return s
          }, 0)
          
          // Sumar abonos del outbox que NO estén ya en la lista de DB (por ID)
          const sumOutbox = abonosOutboxHoy
            .filter(op => op.tarjeta_codigo === t.codigo)
            .reduce((s, op) => {
              // Si el abono de outbox tiene ID y ese ID ya fue visto en la DB, no lo sumamos de nuevo
              if (op.id && seenIds.has(String(op.id))) return s
              return s + Number(op.monto || 0)
            }, 0)

          return [t.codigo, sumDB + sumOutbox]
        })
        
        if (cancelled) return
        const map = Object.fromEntries(entries)
        const tot = Object.values(map).reduce((s,v)=>s+Number(v||0),0)
        const si = (tarjetas||[]).filter(t => Number(map[t.codigo]||0) > 0)
        const no = (tarjetas||[]).filter(t => !map[t.codigo] || Number(map[t.codigo])===0)
        
        // --- 3. TARJETAS CANCELADAS HOY ---
        // Buscar actualizaciones de estado en outbox
        const updatesMap = {}
        outOps.forEach(op => {
          if (op.type === 'tarjeta:update' && op.payload && (op.tarjeta_id || op.codigo)) {
            const cid = String(op.tarjeta_id || op.codigo)
            if (!updatesMap[cid] || op.ts > updatesMap[cid].ts) {
              updatesMap[cid] = { ...op.payload, ts: op.ts }
            }
          }
        })

        const canceladas = (tarjetas || []).filter(t => {
          const update = updatesMap[String(t.codigo)]
          
          // Estado efectivo
          let estado = t.estado
          if (update && update.estado) estado = update.estado
          estado = (estado||'').toLowerCase()
          
          if (estado !== 'cancelada' && estado !== 'canceladas') return false
          
          // Fecha cancelación efectiva
          let fechaCancel = t.fecha_cancelacion ? parseISODateToLocal(String(t.fecha_cancelacion)) : null
          if (update) {
            if (update.fecha_cancelacion) {
              fechaCancel = parseISODateToLocal(String(update.fecha_cancelacion))
            } else if (update.estado === 'cancelada' && !fechaCancel) {
              // Si se canceló en outbox pero no tiene fecha explícita, usar timestamp de la op
              fechaCancel = new Date(update.ts)
            }
          }
          
          if (!fechaCancel) return false
          return formatDateYYYYMMDD(fechaCancel) === today
        })

        setAbonosHoyPorTarjeta(map)
        setTotalHoy(tot)
        setSiAbonan(si)
        setNoAbonan(no)
        setTarjetasNuevas(tarjetasNuevasHoy)
        setCanceladasHoy(canceladas)

      } catch {}
    })()
    return ()=>{ cancelled = true }
  }, [tarjetas, abonosPorTarjeta])

  return (
    <div style={{position:'fixed', inset:0, zIndex:9998, background:'rgba(0,0,0,.6)', display:'grid', placeItems:'center'}} onClick={onClose}>
      <div className="card" style={{maxWidth:720, width:'94%', maxHeight:'86vh', overflow:'hidden', background:'#0e1526', border:'1px solid #1f2a44'}} onClick={(e)=>e.stopPropagation()}>
        <div style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
          <strong>Recaudado hoy</strong>
          <button className="secondary" onClick={onClose}>Cerrar</button>
        </div>
        <div style={{overflowY:'auto', overflowX:'hidden', paddingRight:4}}>
          <div style={{display:'grid', gap:10}}>
            <div className="neon-title">Total: {currency(totalHoy)}</div>
            
            {/* Tarjetas nuevas */}
            {tarjetasNuevas.length > 0 && (
              <div>
                <div className="neon-sub" style={{marginBottom:6}}>Tarjetas nuevas ({tarjetasNuevas.length})</div>
                <div style={{display:'grid', gap:6}}>
                  {tarjetasNuevas.map(t => (
                    <div key={t.codigo} className="val-info">
                      {(t?.cliente?.nombre||'')+' '+(t?.cliente?.apellido||'')} - {currency(t.monto)}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tarjetas canceladas hoy */}
            {canceladasHoy.length > 0 && (
              <div>
                <div className="neon-sub" style={{marginBottom:6, color:'#ef4444'}}>Canceladas hoy ({canceladasHoy.length})</div>
                <div style={{display:'grid', gap:6}}>
                  {canceladasHoy.map(t => (
                    <div key={t.codigo} className="val-info" style={{color:'#fca5a5'}}>
                      {(t?.cliente?.nombre||'')+' '+(t?.cliente?.apellido||'')}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Abonos del día */}
            <div>
              <div className="neon-sub" style={{marginBottom:6}}>Abonos del día ({siAbonan.length})</div>
              <div className="table">
                <div style={{display:'grid', gridTemplateColumns:'1fr auto', gap:8}}>
                  {siAbonan.map(t=> (
                    <div key={t.codigo} style={{display:'contents'}}>
                      <div className="val-pos">{(t?.cliente?.nombre||'')+' '+(t?.cliente?.apellido||'')}</div>
                      <div className="val-pos">{currency(abonosHoyPorTarjeta[t.codigo]||0)}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            
            {/* Tarjetas sin abono */}
            <div>
              <div className="neon-sub" style={{marginBottom:6}}>Tarjetas sin abono ({noAbonan.length})</div>
              <div style={{display:'grid', gap:6}}>
                {noAbonan.map(t => (
                  <div key={t.codigo} className="val-neg">{(t?.cliente?.nombre||'')+' '+(t?.cliente?.apellido||'')}</div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

  return (
    <div className="app-shell tarjetas-page" style={{width:'100%'}}>
      <div className="tarjetas-toolbar-fixed" style={{opacity: hasChildRoute ? 0 : 1, pointerEvents: hasChildRoute ? 'none' : 'auto', transition:'opacity 0.2s ease'}}>
        <div className="tarjetas-toolbar-row">
          <h1>Tarjetas</h1>
          <div style={{fontSize:14, color:'var(--muted)'}}>Tarjetas <b style={{color:'var(--fg)'}}>{tarjetas.length}</b></div>
        </div>
        <div className="tarjetas-toolbar-row">
          <div className="tarjetas-metrics">
            <button onClick={()=>setShowRecaudos(v=>!v)} style={{background:'transparent', color:'var(--fg)', border:'none', padding:0, cursor:'pointer', fontSize:15}}>
              <span style={{opacity:.85}}>Recaudos</span>
            </button>
            <button onClick={()=>setShowRecaudos(v=>!v)} style={{background:'transparent', color:'var(--fg)', border:'none', padding:0, cursor:'pointer', fontSize:16}}>
              <span style={{fontSize:16}}> $ </span><b style={{fontSize:16}}>{currency(stats.monto)}</b>
            </button>
            <button onClick={()=>setShowRecaudos(v=>!v)} style={{background:'transparent', color:'var(--fg)', border:'none', padding:0, cursor:'pointer', fontSize:16}}>
              <span style={{fontSize:16}}> # </span><b style={{fontSize:16}}>{stats.abonos}</b>
            </button>
          </div>
        </div>
        <div className="tarjetas-search">
          <input
            ref={searchInputRef}
            type="search"
            placeholder="Buscar por nombre y apellido..."
            value={query}
            onChange={(e)=>setQuery(e.target.value)}
            onKeyDown={(e)=>{ if (e.key === 'Escape') { e.preventDefault(); setQuery('') } }}
          />
        </div>
      </div>

      <div className="tarjetas-scroll" style={{opacity: hasChildRoute ? 0 : 1, pointerEvents: hasChildRoute ? 'none' : 'auto', transition:'opacity 0.2s ease'}}>
        <section className="tarjetas-list">
          {filtradas.map((t, idx)=>{
          // Obtener abonos reales de la tarjeta y derivar SIEMPRE el resumen dinámico
          const abonos = abonosPorTarjeta[t.codigo] || []
          const resumen = computeDerived(t, abonos, new Date())
            // Mostrar saldo pendiente (no el monto total)
            const saldoPendiente = resumen?.saldo_pendiente || 0
            const dias = resumen?.dias_pasados_cancelacion || 0
            const estado = dias > 0 ? 'Vencida' : 'Vigente'
            const barraColor = dias > 0 ? '#7f1d1d' : '#14532d'
            const nombre = ((t?.cliente?.nombre || '') + ' ' + (t?.cliente?.apellido || '')).trim() || 'Cliente'
            const direccion = t?.cliente?.direccion || ''
            const telefono = t?.cliente?.telefono || t?.telefono || t?.cliente_telefono || ''
            const abonadoHoy = !!abonadosHoyMap[t.codigo]
            const rutaNum = t?.numero_ruta != null ? Number(t.numero_ruta) : null
            const rutaSiguiente = idx < filtradas.length-1 ? Number(filtradas[idx+1]?.numero_ruta ?? null) : null
            return (
              <SwipeableTarjeta key={t.codigo} tarjeta={t} barraColor={barraColor} nombre={nombre} telefono={telefono} direccion={direccion} saldo={saldoPendiente} estadoStr={estado} abonadoHoy={abonadoHoy} rutaNum={rutaNum} hideRuta={showRecaudos}
                data-tarjeta-id={t.codigo} data-ruta={rutaNum != null ? rutaNum : ''}
                onLongPress={(tar)=>{ setAddCtx({ posicionAnterior: rutaNum, posicionSiguiente: rutaSiguiente }); setShowAdd(true) }} />
            )
          })}
        </section>
      </div>
      {showAdd && <AddTarjetaModal posicionAnterior={addCtx.posicionAnterior} posicionSiguiente={addCtx.posicionSiguiente} onClose={()=>setShowAdd(false)} onCreated={()=>{ setShowAdd(false); window.dispatchEvent(new Event('outbox-updated')) }} />}
      {showRecaudos && (
        <RecaudosOverlay tarjetas={tarjetas} abonosPorTarjeta={abonosPorTarjeta} onClose={()=>setShowRecaudos(false)} />
      )}
      {/* Overlay para rutas hijas (detalle/abonos) sin desmontar el listado */}
      {hasChildRoute && (
        <div style={{position:'fixed', inset:0, pointerEvents:'none', zIndex:1000}}>
          <div style={{pointerEvents:'auto', height:'100%', overflow:'auto'}}>
            <Outlet />
          </div>
        </div>
      )}
      {!hasChildRoute && <Outlet />}
    </div>
  )
}

function SwipeableTarjeta({ tarjeta, barraColor, nombre, telefono, direccion, saldo, estadoStr, abonadoHoy, rutaNum, hideRuta, onLongPress, ...restProps }) {
  const navigate = useNavigate()
  // extraer cuotas restantes para limitar el selector de abono
  const resumen = tarjeta?.resumen || computeDerived(tarjeta, [], new Date())
  const totalCuotas = Number(resumen?.cuotas_restantes || 1)
  // Heurística simple: si hay resumen y el saldo es menor al monto total estimado, marcar como abonado (esto se refinará)
  const monto = Number(tarjeta?.monto || 0)
  const interes = Number(tarjeta?.interes || 0)
  const totalEstimado = monto * (1 + interes/100)
  const cuotasTotales = Number(tarjeta?.cuotas || 1)
  const cuotaMonto = cuotasTotales > 0 ? Math.round(totalEstimado / cuotasTotales) : 0
  const saldoEstimado = resumenSaldoEstimado(tarjeta) // fallback para validaciones
  const abonado = Number.isFinite(Number(saldoEstimado)) && totalEstimado && Number(saldoEstimado) < Number(totalEstimado)
  const [offsetX, setOffsetX] = useState(0)
  const [activePanel, setActivePanel] = useState('main') // main | left | right
  const startX = useRef(0)
  const startY = useRef(0)
  const lastX = useRef(0)
  const lastY = useRef(0)
  const startT = useRef(0)
  const cardW = useRef(320)
  const dragging = useRef(false)
  const containerRef = useRef(null)
  const swipeIntent = useRef(null) // null | 'h' | 'v'
  const longPressTimer = useRef(null)
  const longPressTriggered = useRef(false)
  const claseEstadoAbono = abonadoHoy ? 'abonado' : 'no-abono'

  function onTouchStart(e){
    const x = e.touches[0].clientX
    const y = e.touches[0].clientY
    const rect = containerRef.current?.getBoundingClientRect()
    if (rect) cardW.current = rect.width
    dragging.current = true
    startX.current = x
    startY.current = y
    lastX.current = x
    lastY.current = y
    startT.current = performance.now()
    swipeIntent.current = null
    longPressTriggered.current = false
    // long-press para agregar tarjeta con contexto
    clearTimeout(longPressTimer.current)
    longPressTimer.current = setTimeout(()=>{
      // Permitir long-press si no se ha desplazado y seguimos en panel principal
      const totalMoveX = Math.abs(lastX.current - startX.current)
      const totalMoveY = Math.abs(lastY.current - startY.current)
      if (activePanel === 'main' && totalMoveX < 8 && totalMoveY < 8) {
        try { onLongPress?.(tarjeta) } catch {}
        longPressTriggered.current = true
      }
    }, 600)
  }
  function onTouchMove(e){
    if(!dragging.current) return
    const cx = e.touches[0].clientX
    const cy = e.touches[0].clientY
    lastX.current = cx
    lastY.current = cy
    const dx = cx - startX.current
    const dy = cy - startY.current
    // zona muerta inicial un poco mayor para evitar falsos positivos
    if (Math.abs(dx) + Math.abs(dy) < 14) { setOffsetX(0); return }
    // decidir intención una sola vez
    if (swipeIntent.current === null) {
      const horizontal = Math.abs(dx) > Math.abs(dy) * 1.25 // privilegia horizontal
      swipeIntent.current = horizontal ? 'h' : 'v'
    }
    if (swipeIntent.current === 'h') {
      e.preventDefault()
      // Guiar el swipe según el panel actual para evitar "glitches":
      // - Si estoy en LEFT, el gesto útil para volver es hacia la derecha (dx>0)
      // - Si estoy en RIGHT, el gesto útil para volver es hacia la izquierda (dx<0)
      if (activePanel === 'left' && dx < 0) {
        setOffsetX(dx * 0.25) // resistencia
      } else if (activePanel === 'right' && dx > 0) {
        setOffsetX(dx * 0.25) // resistencia
      } else {
        setOffsetX(dx)
      }
    } else {
      setOffsetX(0)
    }
    // mover cancela long-press
    clearTimeout(longPressTimer.current)
  }
  function onTouchEnd(){
    if(!dragging.current){ setOffsetX(0); return }
    dragging.current = false
    const dx = offsetX
    const dt = Math.max(1, performance.now() - startT.current)
    const vx = dx / dt // px/ms
    // Umbrales más permisivos
    const openDist = Math.max(56, cardW.current * 0.18)
    const returnDist = Math.max(28, cardW.current * 0.1)
    const openVel = 0.35
    const returnVel = 0.25

    let opened = false
    if (swipeIntent.current === 'h') {
      if (activePanel === 'main') {
        if (dx <= -openDist || vx <= -openVel) { setActivePanel('left'); opened = true }
        else if (dx >= openDist || vx >= openVel) { setActivePanel('right'); opened = true }
      } else if (activePanel === 'left') {
        if (dx >= returnDist || vx >= returnVel) setActivePanel('main')
      } else if (activePanel === 'right') {
        if (dx <= -returnDist || vx <= -returnVel) setActivePanel('main')
      }
    }
    // Detectar tap confiable: poco movimiento, intención no vertical y panel principal activo
    const totalMoveX = Math.abs(lastX.current - startX.current)
    const totalMoveY = Math.abs(lastY.current - startY.current)
    const isTap = totalMoveX < 8 && totalMoveY < 8 && dt < 400
    if (!opened && isTap && swipeIntent.current !== 'v' && activePanel === 'main' && !longPressTriggered.current) {
      // Guardar solo el número de ruta y fallback simples
      try {
        const ruta = Number.isFinite(Number(rutaNum)) ? Number(rutaNum) : (Number(tarjeta?.numero_ruta) || null)
        if (ruta != null) sessionStorage.setItem('restore_ruta', String(ruta))
        sessionStorage.setItem('last_tarjeta_codigo', String(tarjeta.codigo))
        sessionStorage.setItem('tarjetas_last_scroll', String(window.scrollY || window.pageYOffset || 0))
      } catch {}
      navigate(`/tarjetas/${encodeURIComponent(tarjeta.codigo)}`)
    }
    setOffsetX(0)
    swipeIntent.current = null
    clearTimeout(longPressTimer.current)
    longPressTriggered.current = false
  }
  function closePanels(){ setActivePanel('main') }

  async function handlePagarCuota(monto, metodo){
    const numeric = Number(monto)
    if (!Number.isFinite(numeric) || numeric <= 0) { alert('Monto inválido'); return }
    if (Number.isFinite(Number(saldo)) && numeric > Number(saldo)) { alert('No puedes abonar más que el saldo pendiente'); return }
    const { token: jornadaToken } = getCurrentJornada()
    
    const queued = await offlineDB.queueOperation({ 
      type: 'abono:add', 
      op: 'abono', 
      tarjeta_codigo: tarjeta.codigo, 
      monto: numeric, 
      metodo_pago: metodo, 
      ts: Date.now(),
      session_id: jornadaToken || undefined,
    })
    try {
      const existentes = await offlineDB.getAbonos(tarjeta.codigo)
      const now = Date.now()
      const nuevo = { id: queued.id, fecha: getLocalDateString(), monto: numeric, metodo: metodo, ts: now, session_id: jornadaToken || undefined }
      await offlineDB.setAbonos(tarjeta.codigo, [...(existentes||[]), nuevo])
      window.dispatchEvent(new Event('outbox-updated'))
    } catch {}
    closePanels()
  }
  async function handleResetAbono(){
    try {
      // 1) Eliminar de outbox todos los abonos del día para esta tarjeta
      const out = await offlineDB.readOutbox().catch(()=>[])
      const today = formatDateYYYYMMDD()
      const toRemove = (out||[]).filter(it => it && it.type === 'abono:add' && String(it.tarjeta_codigo) === String(tarjeta.codigo) && it.ts && formatDateYYYYMMDD(new Date(it.ts)) === today)
      // Guardar los IDs para limpiar también la lista de abonos en cache (por id)
      const ids = new Set(toRemove.map(it => it.id))
      for (const it of toRemove) { await offlineDB.removeOutbox(it.id) }

      // 2) Limpiar lista de abonos locales de la tarjeta (coincidentes con hoy y/o IDs recién removidos)
      try {
        const existing = await offlineDB.getAbonos(tarjeta.codigo)
        const filtered = (existing||[]).filter(a => {
          const isIdRemoved = a && a.id && ids.has(a.id)
          const d = a?.fecha ? parseISODateToLocal(String(a.fecha)) : (a?.ts ? new Date(a.ts) : null)
          const isToday = d && formatDateYYYYMMDD(d) === today
          // quitar los del día que correspondían a outbox (por id) o todos los del día si no hay id
          return !(isIdRemoved || isToday)
        })
        await offlineDB.setAbonos(tarjeta.codigo, filtered)
      } catch {}

      // 3) Notificar para refrescar UI
      window.dispatchEvent(new Event('outbox-updated'))
    } catch {}
    closePanels()
  }

  return (
    <div className={`neon-card ${claseEstadoAbono}`} style={{width:'100%', overflow:'hidden', position:'relative', WebkitUserSelect:'none', userSelect:'none', touchAction:'pan-y'}} ref={containerRef} {...restProps}
      onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
      {Number.isFinite(rutaNum) && !hideRuta && (
        <div style={{position:'absolute', top:6, left:8, color:'#ef4444', fontWeight:700, fontSize:12, zIndex:60}}>
          {rutaNum}
        </div>
      )}
      <div className="neon-topbar" style={{background: barraColor}} />
      {/* Panel principal */}
      <div style={{transform:`translateX(${activePanel==='left'?-100: activePanel==='right'?100:0}% ) translateX(${offsetX}px)`, transition: dragging.current ? 'none' : 'transform .25s cubic-bezier(.22,.61,.36,1)'}}>
        <div style={{display:'flex', flexDirection:'column', alignItems:'center', padding:16}}>
          <div className={`neon-avatar ${abonadoHoy ? 'neon-avatar--abonado' : 'neon-avatar--noabono'}`}>{(nombre[0]||'U').toUpperCase()}</div>
          <div className="neon-title" style={{textAlign:'center'}}>{nombre}</div>
          {telefono ? (
            <div className="neon-sub" style={{textAlign:'center'}}>Tel: <span className="val-num">{telefono}</span></div>
          ) : (
            <div className="neon-sub" style={{textAlign:'center'}}>Tel: —</div>
          )}
          <TarjetaIdentificacion tarjeta={tarjeta} />
          <div className="neon-saldo" style={{textAlign:'center'}}>{formatMoney(saldo)}</div>
          <div style={{marginTop:6}}><span className="badge" style={{background:barraColor, color:'#fff'}}>{estadoStr}</span></div>
        </div>
      </div>
      {/* Panel izquierdo sobre la tarjeta */}
      <div style={{position:'absolute', inset:0, transform:`translateX(${activePanel==='left'? 0 : -100}%)`, transition:'transform .25s cubic-bezier(.22,.61,.36,1)', zIndex:50}}>
        <PanelPago onClose={closePanels} onPagar={handlePagarCuota} onReset={handleResetAbono} maxCuotas={totalCuotas} cuotaMonto={cuotaMonto} saldoRestante={Number(saldo)} />
      </div>
      {/* Panel derecho sobre la tarjeta */}
      <div style={{position:'absolute', inset:0, transform:`translateX(${activePanel==='right'? 0 : 100}%)`, transition:'transform .25s cubic-bezier(.22,.61,.36,1)', zIndex:50}}>
        <PanelContacto telefono={telefono} onClose={closePanels} />
      </div>
    </div>
  )
}

function resumenSaldoEstimado(tarjeta){
  try {
    const monto = Number(tarjeta?.monto || 0)
    const interes = Number(tarjeta?.interes || 0)
    const cuotas = Number(tarjeta?.cuotas || 0)
    const total = monto * (1 + interes/100)
    const abonos = 0
    return Math.max(0, total - abonos)
  } catch { return null }
}

function PanelPago({ onClose, onPagar, onReset, maxCuotas = 99, cuotaMonto = 0, saldoRestante = 0 }) {
  const [cuotas, setCuotas] = useState(1)
  const cuotaSugerida = Math.max(0, Math.round(Number(cuotaMonto)||0))
  const [montoBase, setMontoBase] = useState(() => formatMoney(Math.max(0, Math.min(Number(saldoRestante)||0, cuotaSugerida))))
  const [metodo, setMetodo] = useState('efectivo')
  useEffect(() => {
    // Asegurar que siempre haya un método válido seleccionado
    if (metodo !== 'efectivo' && metodo !== 'consignacion') {
      setMetodo('efectivo')
    }
  }, [metodo])
  useEffect(() => {
    // Si el saldo restante es menor a la cuota, sugerir el saldo restante
    const s = Number(saldoRestante)||0
    const sugerido = Math.max(0, Math.min(s, cuotaSugerida))
    setMontoBase(formatMoney(sugerido))
  }, [saldoRestante, cuotaSugerida])
  const total = Number((montoBase||'').toString().replace(/[^0-9]/g,''))
  function onWheel(e){
    e.preventDefault(); e.stopPropagation()
    const delta = Math.sign(e.deltaY)
    setCuotas(c => {
      let next = c - delta
      if (next < 1) next = maxCuotas
      if (next > maxCuotas) next = 1
      if (next !== c) {
        playTick()
        setMontoBase(formatMoney(Math.max(0, Math.round((Number(cuotaMonto)||0) * next))))
      }
      return next
    })
  }
  function playTick(){
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      const o = ctx.createOscillator()
      const g = ctx.createGain()
      o.type = 'square'; o.frequency.value = 900
      g.gain.setValueAtTime(0.12, ctx.currentTime)
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.06)
      o.connect(g).connect(ctx.destination)
      o.start(); o.stop(ctx.currentTime + 0.06)
    } catch {}
  }
  const spinStartY = useRef(0)
  function onSpinTouchStart(e){
    e.preventDefault(); e.stopPropagation();
    spinStartY.current = e.touches[0].clientY
  }
  function onSpinTouchMove(e){
    e.preventDefault(); e.stopPropagation();
    const y = e.touches[0].clientY
    const dy = y - spinStartY.current
    if (Math.abs(dy) > 18) {
      setCuotas(c => {
        let next = dy > 0 ? (c - 1) : (c + 1)
        if (next < 1) next = maxCuotas
        if (next > maxCuotas) next = 1
        if (next !== c) {
          playTick()
          setMontoBase(formatMoney(Math.max(0, Math.round((Number(cuotaMonto)||0) * next))))
        }
        return next
      })
      spinStartY.current = y
    }
  }
  // UX: arriba debe sugerir "sube (ascendente)" y abajo "baja (descendente)"
  const prevQ = cuotas === 1 ? maxCuotas : (cuotas - 1)
  const nextQ = cuotas === maxCuotas ? 1 : (cuotas + 1)
  return (
    <div style={{position:'absolute', inset:0, background:'#0e1526', display:'grid', gridTemplateColumns:'96px 1fr', alignItems:'start', gap:8, padding:'8px 8px 10px 8px', minHeight:300, maxHeight:'60vh', overflow:'hidden'}}>
      {/* Selector de cuotas (área táctil más amplia) */}
      <div style={{display:'flex', alignItems:'flex-start', justifyContent:'center', marginTop:12}}>
        <div
          onWheel={onWheel}
          onTouchStart={onSpinTouchStart}
          onTouchMove={onSpinTouchMove}
          style={{
            touchAction:'none',
            width:86,
            padding:'12px 0',
            borderRadius:14,
            border:'1px solid rgba(59,130,246,0.35)',
            background:'rgba(255,255,255,0.04)',
            display:'flex',
            flexDirection:'column',
            alignItems:'center',
            justifyContent:'flex-start',
            gap:2,
          }}
        >
          <div style={{opacity:.55, fontSize:12, height:26, display:'grid', placeItems:'center'}}>{nextQ}</div>
          <div style={{fontSize:22, fontWeight:800, height:30, display:'grid', placeItems:'center'}}>{cuotas}</div>
          <div style={{opacity:.55, fontSize:12, height:26, display:'grid', placeItems:'center'}}>{prevQ}</div>
          <div style={{marginTop:10, fontSize:10, opacity:.55}}>Desliza</div>
        </div>
      </div>
      {/* Radios pequeños arriba, input inmediatamente debajo, botones al fondo */}
      <div style={{display:'grid', gridTemplateRows:'auto auto auto', gap:6}}>
        <div style={{display:'flex', gap:8, justifyContent:'center', alignItems:'center', flexWrap:'wrap'}}>
          <div role="group" aria-label="Método de pago" style={{display:'flex', border:'1px solid #223045', borderRadius:10, overflow:'hidden'}}>
            <button type="button"
              onClick={()=>setMetodo('efectivo')}
              aria-pressed={metodo==='efectivo'}
              style={{
                padding:'6px 10px', fontSize:13, cursor:'pointer',
                background: metodo==='efectivo' ? '#14532d' : 'transparent', /* verde */
                color: metodo==='efectivo' ? '#fff' : 'var(--fg)',
                border:'none'
              }}>Efectivo</button>
            <button type="button"
              onClick={()=>setMetodo('consignacion')}
              aria-pressed={metodo==='consignacion'}
              style={{
                padding:'6px 10px', fontSize:13, cursor:'pointer',
                background: metodo==='consignacion' ? '#0c4a6e' : 'transparent', /* azul */
                color: metodo==='consignacion' ? '#fff' : 'var(--fg)',
                border:'none'
              }}>Consignación</button>
          </div>
          <span style={{fontSize:12, color:'var(--muted)'}}>x {cuotas}</span>
        </div>
        <div style={{display:'flex', alignItems:'center', justifyContent:'center', marginTop:12}}>
          <input type="text" inputMode="numeric" placeholder="$ monto" pattern="[0-9]*"
                 value={montoBase}
                 onChange={(e)=>{
                   const raw = e.target.value.replace(/[^0-9]/g,'')
                   setMontoBase(formatMoney(Number(raw||0)))
                 }}
                 onFocus={(e) => e.target.select()}
                 style={{width:'100%', maxWidth:420, background:'#0b1220', color:'var(--fg)', border:'1px solid #3b82f6', borderRadius:10, padding:'6px 8px'}}/>
        </div>
        <div style={{display:'flex', gap:22, flexWrap:'nowrap', justifyContent:'center', alignItems:'center', marginTop:32}}>
          <button className="neon-btn" aria-label="Volver" title="Volver" style={{padding:'8px', width:44, height:44, display:'grid', placeItems:'center', background:'#7f1d1d'}} onClick={onClose}>
            <X size={22} />
          </button>
          <button className="neon-btn" aria-label="Aceptar" title="Aceptar" style={{padding:'8px', width:44, height:44, display:'grid', placeItems:'center', background:'#14532d'}} onClick={()=>{
            const numeric = Number((montoBase||'').toString().replace(/[^0-9]/g,''))
            onPagar(numeric, metodo)
          }}>
            <Check size={22} />
          </button>
          <button className="neon-btn" aria-label="Resetear" title="Resetear" style={{padding:'8px', width:44, height:44, display:'grid', placeItems:'center', background:'#1e3a8a'}} onClick={onReset}>
            <RotateCw size={22} />
          </button>
        </div>
      </div>
    </div>
  )
}

function PanelContacto({ telefono, onClose }) {
  const tel = (telefono||'').toString().replace(/\s/g,'')
  const whatsapp = tel ? `https://wa.me/${tel.replace(/[^0-9]/g,'')}` : '#'
  const llamar = tel ? `tel:${tel}` : '#'
  return (
    <div style={{position:'absolute', inset:0, background:'#0e1526', display:'flex', flexDirection:'column', justifyContent:'center', alignItems:'center', gap:12, padding:16}}>
      <div className="neon-title">Contacto</div>
      <div className="neon-sub">Teléfono: {telefono||'—'}</div>
      <div style={{display:'flex', gap:10, flexWrap:'wrap', justifyContent:'center'}}>
        <a className="neon-btn" href={llamar}>Llamar</a>
        <a className="neon-btn" href={whatsapp} target="_blank" rel="noreferrer">WhatsApp</a>
        <button className="neon-btn" onClick={onClose}>Volver</button>
      </div>
    </div>
  )
}

function TarjetaIdentificacion({ tarjeta }){
  const id = tarjeta?.cliente_identificacion || tarjeta?.cliente?.identificacion || tarjeta?.cliente?.cedula || ''
  return (
    <div className="neon-sub" style={{textAlign:'center'}}>ID: {id || '—'}</div>
  )
}
