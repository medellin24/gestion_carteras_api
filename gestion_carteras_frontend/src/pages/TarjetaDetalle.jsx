import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
// API deshabilitada en detalle para evitar llamadas post-descarga
import { offlineDB } from '../offline/db.js'
import { computeDerived } from '../utils/derive.js'

function currency(n){ try { return new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(n||0) } catch { return `$${Number(n||0).toFixed(0)}` } }

export default function TarjetaDetallePage(){
  const { codigo } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [cliente, setCliente] = useState(null)
  const [resumen, setResumen] = useState(null)
  const [error, setError] = useState('')

  useEffect(()=>{
    async function load(){
      try{
        // Primero intentar offline
        const [tarjetas, abonos] = await Promise.all([
          offlineDB.getTarjetas().catch(()=>[]),
          offlineDB.getAbonos(codigo).catch(()=>[]),
        ])
        const tLocal = (tarjetas||[]).find(t => String(t.codigo) === String(codigo))
        if (tLocal) {
          setData(tLocal)
          setResumen(computeDerived(tLocal, abonos, new Date()))
        }
        // No se realizan llamadas a la API aquí; el detalle usa únicamente datos locales
      }catch(e){ setError(e?.message||'Error cargando tarjeta') }
    }
    load()
  },[codigo])

  if (error) return <div className="app-shell"><header className="app-header"><h1>Detalle</h1></header><main><div className="error">{error}</div></main></div>
  if (!data) return <div className="app-shell"><header className="app-header"><h1>Detalle</h1></header><main><div className="card">Cargando…</div></main></div>

  const nombre = ((cliente?.nombre || data?.cliente?.nombre || '') + ' ' + (cliente?.apellido || data?.cliente?.apellido || '')).trim()
  const telefono = (cliente?.telefono || data?.cliente?.telefono || data?.telefono) || '—'
  const direccion = (cliente?.direccion || data?.cliente?.direccion) || '—'
  const identificacion = data?.cliente_identificacion || cliente?.identificacion || cliente?.cedula || data?.cliente?.identificacion || data?.cliente?.cedula || '—'

  const fecha_creacion = data?.fecha_creacion || '—'
  const monto = (data?.monto || 0) * (1 + Number(data?.interes||0)/100)
  const cuotas = data?.cuotas || 0
  const abonado = resumen?.total_abonado || 0
  const saldo = resumen?.saldo_pendiente || 0
  const cuotas_restantes = resumen?.cuotas_restantes || 0
  const dias_venc = resumen?.dias_pasados_cancelacion || 0
  const abono_del_dia = resumen?.abono_del_dia || 0
  const cuotas_adelantadas = resumen?.cuotas_adelantadas || 0
  const cuotas_atrasadas = resumen?.cuotas_atrasadas || 0
  const fecha_venc = resumen?.fecha_vencimiento || '—'

  return (
    <div className="app-shell">
      <header className="app-header"><h1>Detalle de Tarjeta</h1></header>
      <main>
        <div className="card" style={{maxWidth:680}}>
          <strong>Cliente</strong>
          <div>Nombre: {nombre || '—'}</div>
          <div>Identificación: <span className="val-num">{identificacion}</span></div>
          <div>Teléfono: <span className="val-num">{telefono}</span></div>
          <div>Dirección: {direccion}</div>
        </div>
        <div className="card" style={{maxWidth:680}}>
          <strong>Préstamo</strong>
          <div>Fecha creación: <span className="val-date">{String(fecha_creacion).replace(/T.*$/,'')}</span></div>
          <div>Préstamo (con interés): <span className="val-num">{currency(monto)}</span></div>
          <div>Cuotas: <span className="val-num">{cuotas}</span></div>
          <div>Abonado: <span className="val-num">{currency(abonado)}</span></div>
          <div>Saldo: <span className="val-num">{currency(saldo)}</span></div>
          <div>Cuotas restantes: <span className="val-num">{cuotas_restantes}</span></div>
        </div>
        <div className="card" style={{maxWidth:680}}>
          <strong>Pago (estado)</strong>
          <div>Abono del día: <span className="val-pos">{currency(abono_del_dia)}</span></div>
          <div>Cuotas atrasadas/adelantadas: <span className={cuotas_atrasadas>0?"val-neg":"val-num"}>{cuotas_atrasadas}</span> / <span className={cuotas_adelantadas>0?"val-pos":"val-num"}>{cuotas_adelantadas}</span></div>
          <div>Días pasados de vencimiento: <span className={dias_venc>0?"val-neg":"val-num"}>{dias_venc}</span></div>
          <div>Fecha vencimiento: <span className="val-date">{String(fecha_venc).replace(/T.*$/,'')}</span></div>
        </div>
        <button className="primary" onClick={()=>navigate(`/tarjetas/${encodeURIComponent(codigo)}/abonos`)}>Listado de abonos</button>
      </main>
    </div>
  )
}
