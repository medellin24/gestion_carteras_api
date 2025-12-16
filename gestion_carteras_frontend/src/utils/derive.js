function parseISODateToLocal(dateStr) {
  if (!dateStr) return null
  try {
    // YYYY-MM-DD => local day
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      const [y, m, d] = dateStr.split('-').map(Number)
      return new Date(y, m - 1, d)
    }
    // ISO con zona explícita
    if (/[zZ]|[\+\-]\d{2}:\d{2}$/.test(dateStr)) {
    const d = new Date(dateStr)
    return isNaN(d.getTime()) ? null : d
    }
    // ISO con 'T' sin zona -> tratar como UTC naive
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?$/.test(dateStr)) {
      const d = new Date(dateStr + 'Z')
      return isNaN(d.getTime()) ? null : d
    }
    const d = new Date(dateStr)
    return isNaN(d.getTime()) ? null : d
  } catch { return null }
}

function startOfDay(d) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

function diffDays(a, b) {
  const ms = startOfDay(a).getTime() - startOfDay(b).getTime()
  return Math.floor(ms / (24 * 60 * 60 * 1000))
}

function addDays(d, n) {
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}

function normModalidad(mod) {
  const m = String(mod || 'diario').trim().toLowerCase()
  if (m === 'diario' || m === 'semanal' || m === 'quincenal' || m === 'mensual') return m
  return 'diario'
}

function abonoLabelFor(mod) {
  const m = normModalidad(mod)
  if (m === 'semanal') return 'Abono de la semana'
  if (m === 'quincenal') return 'Abono de la quincena'
  if (m === 'mensual') return 'Abono del mes'
  return 'Abono del día'
}

function toYYYYMMDD(d) {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

export function computeLoanTotals(tarjeta) {
  const principal = Number(tarjeta?.monto || 0)
  const interes = Number(tarjeta?.interes || 0)
  const cuotas = Math.max(0, Number(tarjeta?.cuotas || 0))
  const total = principal * (1 + interes / 100)
  const cuotaMonto = cuotas > 0 ? total / cuotas : 0
  return { total, cuotaMonto, cuotas }
}

export function sumAbonos(abonos) {
  return (abonos || []).reduce((s, a) => s + Number(a?.monto || 0), 0)
}

export function sumAbonosDelDia(abonos, hoy = new Date()) {
  const today = toYYYYMMDD(hoy)
  return (abonos || [])
    .filter(a => {
      const d = a?.fecha ? parseISODateToLocal(String(a.fecha)) : (a?.ts ? new Date(a.ts) : null)
      return d && toYYYYMMDD(d) === today
    })
    .reduce((s, a) => s + Number(a?.monto || 0), 0)
}

function sumAbonosEnRango(abonos, startIncl, endExcl) {
  const a0 = startOfDay(startIncl).getTime()
  const b0 = startOfDay(endExcl).getTime()
  return (abonos || [])
    .filter(a => {
      const d = a?.fecha ? parseISODateToLocal(String(a.fecha)) : (a?.ts ? new Date(a.ts) : null)
      if (!d) return false
      const t = startOfDay(d).getTime()
      return t >= a0 && t < b0
    })
    .reduce((s, a) => s + Number(a?.monto || 0), 0)
}

export function computeDerived(tarjeta, abonos = [], hoy = new Date()) {
  const { total, cuotaMonto, cuotas } = computeLoanTotals(tarjeta)
  const fechaCreacion = parseISODateToLocal(String(tarjeta?.fecha_creacion || '')) || new Date(0)
  const modalidad = normModalidad(tarjeta?.modalidad_pago)
  const totalAbonado = sumAbonos(abonos)
  const saldoPendiente = Math.max(0, total - totalAbonado)
  const cuotasPagadasExactas = cuotaMonto > 0 ? totalAbonado / cuotaMonto : 0
  const cuotasPagadas = Math.floor(cuotasPagadasExactas)
  const diasTranscurridos = Math.max(0, diffDays(hoy, fechaCreacion))
  // Periodicidad: cuotas esperadas según modalidad
  let periodosTranscurridos = 0
  let fechaVencimiento = null
  let periodoInicio = null
  let periodoFin = null
  if (modalidad === 'diario') {
    periodosTranscurridos = diasTranscurridos
    fechaVencimiento = cuotas > 0 ? addDays(fechaCreacion, cuotas) : null
    periodoInicio = startOfDay(hoy)
    periodoFin = addDays(periodoInicio, 1)
  } else if (modalidad === 'semanal') {
    periodosTranscurridos = Math.floor(diasTranscurridos / 7)
    fechaVencimiento = cuotas > 0 ? addDays(fechaCreacion, cuotas * 7) : null
    const ini = addDays(fechaCreacion, periodosTranscurridos * 7)
    periodoInicio = startOfDay(ini)
    periodoFin = addDays(periodoInicio, 7)
  } else if (modalidad === 'quincenal') {
    periodosTranscurridos = Math.floor(diasTranscurridos / 15)
    fechaVencimiento = cuotas > 0 ? addDays(fechaCreacion, cuotas * 15) : null
    const ini = addDays(fechaCreacion, periodosTranscurridos * 15)
    periodoInicio = startOfDay(ini)
    periodoFin = addDays(periodoInicio, 15)
  } else { // mensual
    // Regla solicitada: mensual = cada 30 días (no mes calendario)
    periodosTranscurridos = Math.floor(diasTranscurridos / 30)
    fechaVencimiento = cuotas > 0 ? addDays(fechaCreacion, cuotas * 30) : null
    const ini = addDays(fechaCreacion, periodosTranscurridos * 30)
    periodoInicio = startOfDay(ini)
    periodoFin = addDays(periodoInicio, 30)
  }

  const cuotasEsperadas = Math.min(cuotas, periodosTranscurridos)
  const cuotasRestantes = Math.max(0, cuotas - cuotasPagadas)
  const cuotasBalanceDecimal = cuotaMonto > 0
    ? Number(((totalAbonado - (cuotasEsperadas * cuotaMonto)) / cuotaMonto).toFixed(2))
    : 0
  const diasPasadosVenc = fechaVencimiento ? Math.max(0, diffDays(hoy, fechaVencimiento)) : 0
  // Cuotas completas restantes y saldo parcial restante (si la división no es exacta)
  const cuotasRestantesCompletas = cuotaMonto > 0 ? Math.max(0, Math.floor(saldoPendiente / cuotaMonto)) : 0
  const saldoRestanteParcialRaw = Math.max(0, saldoPendiente - (cuotasRestantesCompletas * cuotaMonto))
  const saldoRestanteParcial = Number(saldoRestanteParcialRaw.toFixed(2))
  const abonoDelDia = sumAbonosDelDia(abonos, hoy)
  const abonoDelPeriodo = (periodoInicio && periodoFin)
    ? sumAbonosEnRango(abonos, periodoInicio, periodoFin)
    : (modalidad === 'diario' ? abonoDelDia : 0)
  const cuotasAdelantadas = cuotasBalanceDecimal > 0 ? cuotasBalanceDecimal : 0
  const cuotasAtrasadas = cuotasBalanceDecimal < 0 ? Math.abs(cuotasBalanceDecimal) : 0

  return {
    modalidad_pago: modalidad,
    total_abonado: totalAbonado,
    saldo_pendiente: saldoPendiente,
    cuotas_restantes: cuotasRestantes,
    cuotas_adelantadas: cuotasAdelantadas,
    cuotas_atrasadas: cuotasAtrasadas,
    dias_pasados_cancelacion: diasPasadosVenc,
    fecha_vencimiento: fechaVencimiento ? toYYYYMMDD(fechaVencimiento) : null,
    abono_del_dia: abonoDelDia,
    abono_del_periodo: abonoDelPeriodo,
    abono_label: abonoLabelFor(modalidad),
    cuota_monto: cuotaMonto,
    cuotas_restantes_completas: cuotasRestantesCompletas,
    saldo_restante: saldoRestanteParcial,
    cuotas_balance_decimal: cuotasBalanceDecimal,
    periodo_inicio: periodoInicio ? toYYYYMMDD(periodoInicio) : null,
    periodo_fin: periodoFin ? toYYYYMMDD(periodoFin) : null,
  }
}


