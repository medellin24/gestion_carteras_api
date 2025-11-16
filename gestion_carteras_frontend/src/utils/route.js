const MIN_ROUTE = 1
const MAX_ROUTE = 9999

const clampRoute = (n) => Math.max(MIN_ROUTE, Math.min(MAX_ROUTE, n))

const normalizeRoute = (value) => {
  if (value === null || value === undefined || value === '') return null
  const parsed = parseInt(String(value), 10)
  return Number.isFinite(parsed) ? parsed : null
}

const findGapBetween = (low, high, used) => {
  if (!Number.isFinite(high)) return null
  const start = Math.max(MIN_ROUTE, Math.floor(low) + 1)
  const end = Math.min(MAX_ROUTE, Math.floor(high) - 1)
  if (end < start) return null
  for (let cand = start; cand <= end; cand++) {
    if (!used.has(cand)) return cand
  }
  return null
}

const findFreeAscending = (start, used) => {
  const begin = Math.max(MIN_ROUTE, Math.floor(start))
  for (let cand = begin; cand <= MAX_ROUTE; cand++) {
    if (!used.has(cand)) return cand
  }
  return MAX_ROUTE
}

const findFreeDescending = (start, used) => {
  const begin = Math.min(MAX_ROUTE, Math.floor(start))
  for (let cand = begin; cand >= MIN_ROUTE; cand--) {
    if (!used.has(cand)) return cand
  }
  return MIN_ROUTE
}

const nextHundredAbove = (value) => {
  if (!Number.isFinite(value)) return null
  return Math.floor(value / 100) * 100 + 100
}

export function computeNextRouteNumber(existingRoutes = [], posicionAnterior = null, posicionSiguiente = null) {
  try {
    const routes = Array.from(new Set((existingRoutes || [])
      .map(normalizeRoute)
      .filter((n) => n != null && n >= MIN_ROUTE && n <= MAX_ROUTE)))
      .sort((a, b) => a - b)

    if (routes.length === 0) return 100

    const used = new Set(routes)
    const first = routes[0]
    const last = routes[routes.length - 1]
    const baseRoute = normalizeRoute(posicionAnterior)
    const nextRoute = normalizeRoute(posicionSiguiente)

    const pickBetween = (lower, upper) => {
      if (!Number.isFinite(upper)) return null
      const low = Number.isFinite(lower) ? lower : 0
      if (upper - low <= 1) return findGapBetween(low, upper, used)
      let candidate = Math.floor((low + upper) / 2)
      if (candidate <= low) candidate = low + 1
      if (candidate >= upper) candidate = upper - 1
      candidate = clampRoute(candidate)
      if (candidate > low && candidate < upper && !used.has(candidate)) return candidate
      return findGapBetween(low, upper, used)
    }

    const pickAfter = (reference) => {
      let cursor = Number.isFinite(reference) ? reference : 0
      let candidate = nextHundredAbove(cursor)
      while (candidate && candidate <= MAX_ROUTE) {
        if (!used.has(candidate)) return candidate
        if (candidate === cursor) break
        cursor = candidate
        candidate = nextHundredAbove(cursor)
      }
      return findFreeAscending(Math.max(cursor + 1, (Number.isFinite(reference) ? reference + 1 : MIN_ROUTE)), used)
    }

    // Escenario 1: insertar antes de la primera tarjeta ("poner de primera")
    if (baseRoute == null && nextRoute != null && nextRoute === first) {
      const candidate = pickBetween(0, nextRoute)
      if (candidate != null) return candidate
      return findFreeDescending(nextRoute - 1, used)
    }

    // Escenario 2: insertar entre la tarjeta seleccionada y la siguiente
    if (baseRoute != null && nextRoute != null) {
      const candidate = pickBetween(baseRoute, nextRoute)
      if (candidate != null) return candidate
      return pickAfter(Math.max(baseRoute, nextRoute))
    }

    // Escenario 3: insertar después de la última (sin siguiente)
    if (baseRoute != null && nextRoute == null) {
      return pickAfter(baseRoute)
    }

    // Caso genérico: solo tenemos referencia del siguiente
    if (baseRoute == null && nextRoute != null) {
      const previous = routes.filter(r => r < nextRoute).pop()
      if (previous != null) {
        const candidate = pickBetween(previous, nextRoute)
        if (candidate != null) return candidate
      }
      const candidate = pickBetween(0, nextRoute)
      if (candidate != null) return candidate
      return findFreeDescending(nextRoute - 1, used)
    }

    // Sin contexto: extender después de la última ruta conocida
    return pickAfter(last)
  } catch {
    return 100
  }
}

