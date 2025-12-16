import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
// API deshabilitada en detalle para evitar llamadas post-descarga
import { offlineDB } from '../offline/db.js'
import { computeDerived } from '../utils/derive.js'
import { parseISODateToLocal, formatDateYYYYMMDD } from '../utils/date.js'

function currency(n){ try { return new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(n||0) } catch { return `$${Number(n||0).toFixed(0)}` } }
function formatDecimal(value){
  const num = Number(value || 0)
  try {
    return num.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  } catch {
    return num.toFixed(2)
  }
}

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
  const fecha_creacion_fmt = (() => {
    try {
      const d = typeof fecha_creacion === 'string' ? parseISODateToLocal(fecha_creacion) : (fecha_creacion ? new Date(fecha_creacion) : null)
      return d ? formatDateYYYYMMDD(d) : '—'
    } catch { return '—' }
  })()
  const monto = (data?.monto || 0) * (1 + Number(data?.interes||0)/100)
  const cuotas = data?.cuotas || 0
  const abonado = resumen?.total_abonado || 0
  const saldo = resumen?.saldo_pendiente || 0
  const dias_venc = resumen?.dias_pasados_cancelacion || 0
  const modalidad = (resumen?.modalidad_pago || data?.modalidad_pago || 'diario')
  const abono_del_dia = resumen?.abono_del_dia || 0
  const abono_periodo = (Number.isFinite(resumen?.abono_del_periodo) ? resumen?.abono_del_periodo : null)
  const abonoLabel = resumen?.abono_label || (String(modalidad).toLowerCase()==='diario' ? 'Abono del día' : 'Abono del período')
  const abonoMostrar = abono_periodo != null ? abono_periodo : abono_del_dia
  const cuotas_adelantadas = Number(resumen?.cuotas_adelantadas || 0)
  const cuotas_atrasadas = Number(resumen?.cuotas_atrasadas || 0)
  const fecha_venc = resumen?.fecha_vencimiento || '—'
  const cuota_sugerida = resumen?.cuota_monto || (cuotas ? monto / cuotas : 0)
  const unidadCuota = (() => {
    const m = String(modalidad || 'diario').toLowerCase()
    if (m === 'semanal') return 'semanales'
    if (m === 'quincenal') return 'quincenales'
    if (m === 'mensual') return 'mensuales'
    return 'diarias'
  })()
  const cuotas_enteras_restantes = Number.isFinite(resumen?.cuotas_restantes_completas)
    ? resumen?.cuotas_restantes_completas
    : (cuota_sugerida > 0 ? Math.max(0, Math.floor((saldo || 0) / cuota_sugerida)) : 0)
  const saldo_residual = Number.isFinite(resumen?.saldo_restante)
    ? resumen?.saldo_restante
    : Math.max(0, (saldo || 0) - (cuotas_enteras_restantes * (cuota_sugerida || 0)))
  const cuotasRestantesTexto = (() => {
    if (!cuota_sugerida || saldo <= 0) {
      return saldo <= 0 ? 'Cancelada' : String(resumen?.cuotas_restantes || 0)
    }
    if (saldo_residual > 0 && cuotas_enteras_restantes > 0) {
      return `${cuotas_enteras_restantes} cuotas y 1 de ${currency(saldo_residual)}`
    }
    if (saldo_residual > 0 && cuotas_enteras_restantes === 0) {
      return `1 de ${currency(saldo_residual)}`
    }
    return `${cuotas_enteras_restantes} cuotas`
  })()
  const cuotasBalanceTexto = cuotas_adelantadas > 0
    ? `${formatDecimal(cuotas_adelantadas)} adelantado`
    : (cuotas_atrasadas > 0 ? `${formatDecimal(cuotas_atrasadas)} atrasado` : 'Al día')
  const cuotasBalanceClase = cuotas_adelantadas > 0 ? 'val-pos' : (cuotas_atrasadas > 0 ? 'val-neg' : 'val-num')

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
          <div>Fecha creación: <span className="val-date">{fecha_creacion_fmt}</span></div>
          <div>Préstamo (con interés): <span className="val-num">{currency(monto)}</span></div>
          <div>Modalidad de pago: <span className="val-num">{String(modalidad || 'diario')}</span></div>
          <div>Cuotas: <span className="val-num">{cuotas} {unidadCuota} de {currency(cuota_sugerida || 0)}</span></div>
          <div>Abonado: <span className="val-num">{currency(abonado)}</span></div>
          <div>Saldo: <span className="val-num">{currency(saldo)}</span></div>
          <div>Cuotas restantes: <span className="val-num">{cuotasRestantesTexto}</span></div>
        </div>
        <div className="card" style={{maxWidth:680}}>
          <strong>Pago (estado)</strong>
          <div>{abonoLabel}: <span className="val-pos">{currency(abonoMostrar)}</span></div>
          <div>Cuotas atrasadas/adelantadas: <span className={cuotas_atrasadas>0?"val-neg":"val-num"}>{formatDecimal(cuotas_atrasadas)}</span> / <span className={cuotas_adelantadas>0?"val-pos":"val-num"}>{formatDecimal(cuotas_adelantadas)}</span></div>
          <div>Balance de cuotas: <span className={cuotasBalanceClase}>{cuotasBalanceTexto}</span></div>
          <div>Días pasados de vencimiento: <span className={dias_venc>0?"val-neg":"val-num"}>{dias_venc}</span></div>
          <div>Fecha vencimiento: <span className="val-date">{String(fecha_venc).replace(/T.*$/,'')}</span></div>
        </div>
        <button className="primary" onClick={()=>navigate(`/tarjetas/${encodeURIComponent(codigo)}/abonos`)}>Listado de abonos</button>
      </main>
    </div>
  )
}
