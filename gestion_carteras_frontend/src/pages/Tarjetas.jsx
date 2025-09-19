import React, { useMemo, useState, useEffect, useRef } from 'react'
import { tarjetasStore } from '../state/store.js'
import { offlineDB } from '../offline/db.js'
import { formatDateYYYYMMDD, getLocalDateString } from '../utils/date.js'
import { computeDerived } from '../utils/derive.js'
import { useNavigate, Outlet, useLocation } from 'react-router-dom'
import { Check, RotateCw, X, Plus } from 'lucide-react'
import AddTarjetaModal from '../components/AddTarjetaModal.jsx'

function currency(n) { try { return new Intl.NumberFormat('es-CO', { style:'currency', currency:'COP', maximumFractionDigits:0 }).format(n||0) } catch { return `$${Number(n||0).toFixed(0)}` } }
function formatMoney(n){ try { return new Intl.NumberFormat('es-CO', { style:'currency', currency:'COP', maximumFractionDigits:0 }).format(n||0) } catch { return `$${Number(n||0).toFixed(0)}` } }

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
  
  // Detectar si hay una ruta hija activa (detalle o abonos)
  const hasChildRoute = location.pathname !== '/tarjetas'

  useEffect(() => {
    async function refreshData() {
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
      
      // Construir mapa de tarjetas con abonos del día actual (incluye outbox y abonos guardados)
      const today = formatDateYYYYMMDD()
      const map = {}
      let totalMontoHoy = 0
      let totalCountHoy = 0
      try {
        // Marcar por outbox (acciones locales del día) y sumar montos
        const opsHoy = outOps.filter(op => op && op.ts && formatDateYYYYMMDD(new Date(op.ts)) === today)
        opsHoy.sort((a,b)=>a.ts-b.ts).forEach(op => {
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
              const d = a?.fecha ? new Date(a.fecha) : (a?.ts ? new Date(a.ts): null)
              if (d && formatDateYYYYMMDD(d) === today) {
                acc.totHoy += Number(a?.monto||0)
                acc.countHoy += 1
              }
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

function RecaudosOverlay({ tarjetas, onClose }){
  const today = formatDateYYYYMMDD()
  const [abonosHoyPorTarjeta, setAbonosHoyPorTarjeta] = useState({})
  const [totalHoy, setTotalHoy] = useState(0)
  const [noAbonan, setNoAbonan] = useState([])
  const [siAbonan, setSiAbonan] = useState([])
  const [tarjetasNuevas, setTarjetasNuevas] = useState([])

  useEffect(()=>{
    let cancelled = false
    ;(async()=>{
      try {
        // Obtener tarjetas nuevas del outbox (offline)
        const outOps = await offlineDB.readOutbox().catch(()=>[])
        const tarjetasNuevasOffline = outOps.filter(op => 
          op && op.type === 'tarjeta:new' && 
          op.ts && formatDateYYYYMMDD(new Date(op.ts)) === today
        ).map(op => ({
          codigo: op.temp_id || 'temp',
          cliente: op.cliente || {},
          monto: op.monto || 0
        }))
        
        // Obtener tarjetas nuevas de la base de datos (online - ya sincronizadas)
        const tarjetasNuevasOnline = (tarjetas || []).filter(t => {
          const fechaCreacion = t?.fecha_creacion
          if (!fechaCreacion) return false
          // Convertir fecha a string local para comparar
          const fecha = fechaCreacion instanceof Date ? 
            formatDateYYYYMMDD(fechaCreacion) : 
            formatDateYYYYMMDD(new Date(fechaCreacion))
          return fecha === today
        }).map(t => ({
          codigo: t.codigo,
          cliente: t.cliente || {},
          monto: t.monto || 0
        }))
        
        // Combinar ambas fuentes, evitando duplicados por código
        const tarjetasNuevasHoy = [...tarjetasNuevasOnline, ...tarjetasNuevasOffline]
          .filter((t, index, arr) => arr.findIndex(other => other.codigo === t.codigo) === index)
        
        // Obtener abonos del outbox para el día actual
        const abonosOutboxHoy = outOps.filter(op => 
          op && op.op === 'abono' && 
          op.ts && formatDateYYYYMMDD(new Date(op.ts)) === today
        )
        
        const entries = await Promise.all((tarjetas||[]).map(async (t)=>{
          const list = await offlineDB.getAbonos(t.codigo).catch(()=>[])
          const sum = (list||[]).reduce((s,a)=>{
            const d = a?.fecha ? new Date(a.fecha) : (a?.ts ? new Date(a.ts): null)
            return d && formatDateYYYYMMDD(d) === today ? s + Number(a?.monto||0) : s
          }, 0)
          
          // Sumar abonos del outbox para esta tarjeta
          const outboxSum = abonosOutboxHoy
            .filter(op => op.tarjeta_codigo === t.codigo)
            .reduce((s, op) => s + Number(op.monto || 0), 0)
          
          return [t.codigo, sum + outboxSum]
        }))
        if (cancelled) return
        const map = Object.fromEntries(entries)
        const tot = Object.values(map).reduce((s,v)=>s+Number(v||0),0)
        const si = (tarjetas||[]).filter(t => Number(map[t.codigo]||0) > 0)
        const no = (tarjetas||[]).filter(t => !map[t.codigo] || Number(map[t.codigo])===0)
        setAbonosHoyPorTarjeta(map)
        setTotalHoy(tot)
        setSiAbonan(si)
        setNoAbonan(no)
        setTarjetasNuevas(tarjetasNuevasHoy)
      } catch {}
    })()
    return ()=>{ cancelled = true }
  }, [tarjetas])

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
    <div className="app-shell" style={{width:'100%'}}>
      <main style={{width:'100%', overscrollBehaviorY:'contain'}}>
        {/* Bloque fijo: título, fila de métricas y buscador en un solo sticky */}
        <div style={{position:'sticky', top:0, zIndex:19, background:'var(--bg)', width:'100%', opacity: hasChildRoute ? 0 : 1, transition: 'opacity 0.2s ease'}}>
          <div className="app-header" style={{position:'relative', top:0, zIndex:20, width:'100%', padding:'12px'}}>
            <h1 style={{margin:0, fontSize:18}}>Tarjetas</h1>
          </div>
          {/* Fila única: Recaudado ($ y #) a la izquierda, Tarjetas a la derecha */}
          <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'6px 2px', width:'100%', overflowX:'hidden'}}>
            <div style={{display:'flex', alignItems:'center', gap:18, fontSize:15}}>
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
            <div style={{fontSize:14, color:'var(--muted)'}}>Tarjetas <b style={{color:'var(--fg)'}}>{tarjetas.length}</b></div>
          </div>
          {showRecaudos && (
            <RecaudosOverlay tarjetas={tarjetas} onClose={()=>setShowRecaudos(false)} />
          )}
          {/* Buscador a ancho completo */}
          <div style={{padding:'0 2px 6px 2px', width:'100%', overflowX:'hidden'}}>
            <input
              type="search"
              placeholder="Buscar por nombre y apellido..."
              value={query}
              onChange={(e)=>setQuery(e.target.value)}
              style={{
                width:'100%', background:'#0b1220', color:'var(--fg)',
                border:'1px solid #223045', borderRadius:12, padding:'12px 14px', fontSize:16
              }}
            />
          </div>
        </div>

        {/* Eliminado el botón flotante '+' en favor de long-press con contexto */}

        <div style={{display:'flex', flexDirection:'column', gap:10, padding:'8px 2px 12px 2px', width:'100%', overflowX:'hidden', overscrollBehaviorY:'contain', opacity: hasChildRoute ? 0 : 1, transition: 'opacity 0.2s ease'}}>
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
            const anterior = idx > 0 ? Number(filtradas[idx-1]?.numero_ruta ?? null) : null
            const siguiente = idx < filtradas.length-1 ? Number(filtradas[idx+1]?.numero_ruta ?? null) : null
            const rutaNum = t?.numero_ruta != null ? Number(t.numero_ruta) : null
            return (
              <SwipeableTarjeta key={t.codigo} tarjeta={t} barraColor={barraColor} nombre={nombre} telefono={telefono} direccion={direccion} saldo={saldoPendiente} estadoStr={estado} abonadoHoy={abonadoHoy} rutaNum={rutaNum} hideRuta={showRecaudos}
                data-tarjeta-id={t.codigo} data-ruta={rutaNum != null ? rutaNum : ''}
                onLongPress={(tar)=>{ setAddCtx({ posicionAnterior: anterior, posicionSiguiente: siguiente }); setShowAdd(true) }} />
            )
          })}
        </div>
      </main>
      {showAdd && <AddTarjetaModal posicionAnterior={addCtx.posicionAnterior} posicionSiguiente={addCtx.posicionSiguiente} onClose={()=>setShowAdd(false)} onCreated={()=>{ setShowAdd(false); window.dispatchEvent(new Event('outbox-updated')) }} />}
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
      setOffsetX(dx)
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
    
    const queued = await offlineDB.queueOperation({ 
      type: 'abono:add', 
      op: 'abono', 
      tarjeta_codigo: tarjeta.codigo, 
      monto: numeric, 
      metodo_pago: metodo, 
      ts: Date.now() 
    })
    try {
      const existentes = await offlineDB.getAbonos(tarjeta.codigo)
      const nuevo = { id: queued.id, fecha: getLocalDateString(), monto: numeric, metodo: metodo }
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
          const d = a?.fecha ? new Date(a.fecha) : (a?.ts ? new Date(a.ts) : null)
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
  const prevQ = cuotas === 1 ? maxCuotas : (cuotas - 1)
  const nextQ = cuotas === maxCuotas ? 1 : (cuotas + 1)
  return (
    <div style={{position:'absolute', inset:0, background:'#0e1526', display:'grid', gridTemplateColumns:'72px 1fr', alignItems:'start', gap:6, padding:'8px 8px 10px 8px', minHeight:300, maxHeight:'60vh', overflow:'hidden'}} onTouchStart={(e)=>e.stopPropagation()}>
      {/* Number picker vertical estrecho */}
      <div style={{display:'flex', alignItems:'flex-start', justifyContent:'center', touchAction:'none', marginTop:12}}>
        <div onWheel={onWheel} onTouchStart={onSpinTouchStart} onTouchMove={onSpinTouchMove}
             style={{height:'100%', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'flex-start', gap:2}}>
          <div style={{opacity:.55, fontSize:12, height:24, display:'grid', placeItems:'center'}}>{prevQ}</div>
          <div style={{fontSize:20, fontWeight:700, height:28, display:'grid', placeItems:'center'}}>{cuotas}</div>
          <div style={{opacity:.55, fontSize:12, height:24, display:'grid', placeItems:'center'}}>{nextQ}</div>
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
    <div style={{position:'absolute', inset:0, background:'#0e1526', display:'flex', flexDirection:'column', justifyContent:'center', alignItems:'center', gap:12, padding:16}} onTouchStart={(e)=>e.stopPropagation()}>
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
