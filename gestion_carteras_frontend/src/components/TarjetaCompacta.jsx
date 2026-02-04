import React, { useState, useEffect, useRef } from 'react'
import { Check, X, RotateCw } from 'lucide-react'
import { offlineDB } from '../offline/db.js'
import { getLocalDateString } from '../utils/date.js'

function formatMoney(n){ try { return new Intl.NumberFormat('es-CO', { style:'currency', currency:'COP', maximumFractionDigits:0 }).format(n||0) } catch { return `$${Number(n||0).toFixed(0)}` } }

function getCurrentJornada(){
  const token = (typeof localStorage !== 'undefined' && localStorage.getItem('jornada_token')) || ''
  const startedRaw = (typeof localStorage !== 'undefined' && localStorage.getItem('jornada_started_at')) || '0'
  const startedAt = Number(startedRaw)
  return { token, startedAt: Number.isFinite(startedAt) ? startedAt : 0 }
}

export default function TarjetaCompacta({ 
  tarjeta, 
  barraColor, // Color calculado en el padre (verde/rojo según mora)
  nombre, 
  saldo, 
  abonadoHoy, 
  rutaNum,
  onLongPress,
  ...restProps 
}) {
  const [cuotaInput, setCuotaInput] = useState('')
  const [loading, setLoading] = useState(false)
  const monto = Number(tarjeta?.monto || 0)
  const interes = Number(tarjeta?.interes || 0)
  const totalEstimado = monto * (1 + interes/100)
  const cuotasTotales = Number(tarjeta?.cuotas || 1)
  const cuotaMonto = cuotasTotales > 0 ? Math.round(totalEstimado / cuotasTotales) : 0
  
  // Inicializar input con el valor de la cuota sugerida
  useEffect(() => {
    if (!abonadoHoy && !cuotaInput) {
      setCuotaInput(String(cuotaMonto))
    }
  }, [cuotaMonto, abonadoHoy])

  // Color de borde/fondo según estado de abono
  const style = {
    display: 'grid',
    gridTemplateColumns: '40px 1fr 100px 50px', // Ruta | Nombre | Input | Acción
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    background: '#0e1526', // Fondo base oscuro
    borderBottom: '1px solid #1f2a44',
    height: 54, // Aprox 1.4cm para que sea táctil pero compacto
    position: 'relative',
    overflow: 'hidden'
  }

  // Estilo condicional para resaltar abonos de la jornada
  const highlightStyle = abonadoHoy ? {
    background: 'rgba(16, 185, 129, 0.1)', // Verde suave
    borderLeft: '4px solid #10b981'
  } : {
    borderLeft: `4px solid ${barraColor}` // Rojo/Verde según mora (heredado)
  }

  async function handleAbonar() {
    const val = Number(cuotaInput.replace(/[^0-9]/g, ''))
    if (!val || val <= 0) return
    setLoading(true)
    try {
      const { token: jornadaToken } = getCurrentJornada()
      const queued = await offlineDB.queueOperation({ 
        type: 'abono:add', 
        op: 'abono', 
        tarjeta_codigo: tarjeta.codigo, 
        monto: val, 
        metodo_pago: 'efectivo', 
        ts: Date.now(),
        session_id: jornadaToken || undefined,
      })
      // Optimistic update
      const existentes = await offlineDB.getAbonos(tarjeta.codigo)
      const nuevo = { id: queued.id, fecha: getLocalDateString(), monto: val, metodo: 'efectivo', ts: Date.now(), session_id: jornadaToken || undefined }
      await offlineDB.setAbonos(tarjeta.codigo, [...(existentes||[]), nuevo])
      window.dispatchEvent(new Event('outbox-updated'))
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  async function handleReset() {
    if (!confirm('¿Borrar abonos de hoy para este cliente?')) return
    setLoading(true)
    try {
      // 1. Eliminar de outbox
      const out = await offlineDB.readOutbox().catch(()=>[])
      const { token: jornadaToken } = getCurrentJornada()
      // Filtrar por sesión o fecha
      const toRemove = out.filter(it => 
        it && it.type === 'abono:add' && 
        String(it.tarjeta_codigo) === String(tarjeta.codigo) &&
        (it.session_id === jornadaToken || !jornadaToken) // Simplificado para demo
      )
      const ids = new Set(toRemove.map(it => it.id))
      for (const it of toRemove) await offlineDB.removeOutbox(it.id)

      // 2. Eliminar de caché local
      const existing = await offlineDB.getAbonos(tarjeta.codigo)
      const filtered = (existing||[]).filter(a => !(a.id && ids.has(a.id))) // Simplificado
      await offlineDB.setAbonos(tarjeta.codigo, filtered)
      
      window.dispatchEvent(new Event('outbox-updated'))
    } catch {} finally {
      setLoading(false)
    }
  }

  // Long press logic
  const timerRef = useRef(null)
  function onTouchStart() {
    timerRef.current = setTimeout(() => {
      onLongPress?.(tarjeta)
    }, 600)
  }
  function onTouchEnd() {
    clearTimeout(timerRef.current)
  }

  return (
    <div 
      style={{...style, ...highlightStyle}} 
      onTouchStart={onTouchStart} 
      onTouchEnd={onTouchEnd}
      onTouchMove={onTouchEnd} // Cancelar si mueve el dedo
      {...restProps}
    >
      {/* Columna 1: Ruta */}
      <div style={{fontWeight: 'bold', color: '#888', fontSize: 14}}>
        {rutaNum ?? '-'}
      </div>

      {/* Columna 2: Nombre y Saldo */}
      <div style={{overflow: 'hidden'}}>
        <div style={{fontWeight: 600, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 15}}>
          {nombre}
        </div>
        <div style={{fontSize: 11, color: '#aaa'}}>
          Saldo: {formatMoney(saldo)}
        </div>
      </div>

      {/* Columna 3: Input de Cuota */}
      <div>
        <input 
          type="tel" 
          disabled={abonadoHoy}
          value={abonadoHoy ? 'PAGADO' : cuotaInput}
          onChange={(e) => setCuotaInput(e.target.value)}
          onFocus={(e) => e.target.select()}
          placeholder="$"
          style={{
            width: '100%',
            background: abonadoHoy ? 'transparent' : '#0b1220',
            border: abonadoHoy ? 'none' : '1px solid #334155',
            color: abonadoHoy ? '#10b981' : '#fff',
            borderRadius: 6,
            padding: '6px',
            textAlign: 'center',
            fontSize: 14,
            fontWeight: abonadoHoy ? 700 : 400
          }}
        />
      </div>

      {/* Columna 4: Acción */}
      <div style={{display: 'flex', justifyContent: 'center'}}>
        {loading ? (
          <div className="spinner" style={{width:20, height:20}}></div>
        ) : abonadoHoy ? (
          <button 
            onClick={handleReset}
            style={{
              background: '#ef4444', 
              border: 'none', 
              borderRadius: 6, 
              width: 36, 
              height: 36, 
              display: 'grid', 
              placeItems: 'center',
              color: '#fff'
            }}
          >
            <RotateCw size={18} />
          </button>
        ) : (
          <button 
            onClick={handleAbonar}
            style={{
              background: '#10b981', 
              border: 'none', 
              borderRadius: 6, 
              width: 36, 
              height: 36, 
              display: 'grid', 
              placeItems: 'center',
              color: '#fff'
            }}
          >
            <Check size={20} />
          </button>
        )}
      </div>
    </div>
  )
}
