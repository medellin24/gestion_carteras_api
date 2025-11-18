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

export function computeDerived(tarjeta, abonos = [], hoy = new Date()) {
  const { total, cuotaMonto, cuotas } = computeLoanTotals(tarjeta)
  const fechaCreacion = parseISODateToLocal(String(tarjeta?.fecha_creacion || '')) || new Date(0)
  const totalAbonado = sumAbonos(abonos)
  const saldoPendiente = Math.max(0, total - totalAbonado)
  const cuotasPagadasExactas = cuotaMonto > 0 ? totalAbonado / cuotaMonto : 0
  const cuotasPagadas = Math.floor(cuotasPagadasExactas)
  const diasTranscurridos = Math.max(0, diffDays(hoy, fechaCreacion))
  // Periodicidad diaria: una cuota por día
  const cuotasEsperadas = Math.min(cuotas, diasTranscurridos)
  const cuotasRestantes = Math.max(0, cuotas - cuotasPagadas)
  const cuotasBalanceDecimal = cuotaMonto > 0
    ? Number(((totalAbonado - (cuotasEsperadas * cuotaMonto)) / cuotaMonto).toFixed(2))
    : 0
  const fechaVencimiento = cuotas > 0 ? addDays(fechaCreacion, cuotas) : null
  const diasPasadosVenc = fechaVencimiento ? Math.max(0, diffDays(hoy, fechaVencimiento)) : 0
  // Cuotas completas restantes y saldo parcial restante (si la división no es exacta)
  const cuotasRestantesCompletas = cuotaMonto > 0 ? Math.max(0, Math.floor(saldoPendiente / cuotaMonto)) : 0
  const saldoRestanteParcialRaw = Math.max(0, saldoPendiente - (cuotasRestantesCompletas * cuotaMonto))
  const saldoRestanteParcial = Number(saldoRestanteParcialRaw.toFixed(2))
  const abonoDelDia = sumAbonosDelDia(abonos, hoy)
  const cuotasAdelantadas = cuotasBalanceDecimal > 0 ? cuotasBalanceDecimal : 0
  const cuotasAtrasadas = cuotasBalanceDecimal < 0 ? Math.abs(cuotasBalanceDecimal) : 0

  return {
    total_abonado: totalAbonado,
    saldo_pendiente: saldoPendiente,
    cuotas_restantes: cuotasRestantes,
    cuotas_adelantadas: cuotasAdelantadas,
    cuotas_atrasadas: cuotasAtrasadas,
    dias_pasados_cancelacion: diasPasadosVenc,
    fecha_vencimiento: fechaVencimiento ? toYYYYMMDD(fechaVencimiento) : null,
    abono_del_dia: abonoDelDia,
    cuota_monto: cuotaMonto,
    cuotas_restantes_completas: cuotasRestantesCompletas,
    saldo_restante: saldoRestanteParcial,
    cuotas_balance_decimal: cuotasBalanceDecimal,
  }
}


