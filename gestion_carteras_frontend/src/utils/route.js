export function computeNextRouteNumber(existingRoutes = [], posicionAnterior = null, posicionSiguiente = null) {
  try {
    const routes = Array.from(new Set((existingRoutes || [])
      .map(v => parseInt(String(v), 10))
      .filter(n => Number.isFinite(n) && n >= 0)))
      .sort((a,b)=>a-b)

    if (routes.length === 0) return 100

    const used = new Set(routes)
    const pa = posicionAnterior != null ? parseInt(String(posicionAnterior), 10) : null
    const ps = posicionSiguiente != null ? parseInt(String(posicionSiguiente), 10) : null

    // Detectar si estamos en primera o última tarjeta
    const esPrimera = pa === null && ps === routes[0]
    const esUltima = pa === routes[routes.length - 1] && ps === null

    // Caso intermedio: entre pa y ps
    if (pa != null && ps != null && !esPrimera && !esUltima) {
      if (ps - pa > 1) {
        const mitad = Math.floor((pa + ps) / 2)
        if (mitad > pa && mitad < ps && !used.has(mitad)) return mitad
        // Si la mitad está ocupada, probar uno abajo o uno arriba
        if (mitad - 1 > pa && !used.has(mitad - 1)) return mitad - 1
        if (mitad + 1 < ps && !used.has(mitad + 1)) return mitad + 1
      }
      // Si no hay espacio, buscar siguiente centena disponible
      const base = Math.max(pa, ps)
      let cand = Math.min(((Math.floor(base / 100) + 1) * 100), 9900)
      if (!used.has(cand)) return cand
      // Si está ocupada, buscar siguiente decena
      let d = Math.min(((Math.floor((cand + 1) / 10) * 10)), 9990)
      while (d <= 9999) {
        if (!used.has(d)) return d
        d += 10
      }
      // Último recurso: siguiente libre
      for (let c = base + 1; c <= 9999; c++) if (!used.has(c)) return c
      return 9999
    }

    // Caso última tarjeta: buscar siguiente centena mayor
    if (esUltima || (pa != null && routes.indexOf(pa) === routes.length - 1)) {
      // Ejemplo: si pa=1400, buscar 1500; si pa=9900, buscar 9910
      let cand = Math.min(((Math.floor(pa / 100) + 1) * 100), 9900)
      if (cand === pa) {
        // Si pa ya es una centena (ej: 9900), buscar siguiente decena
        let d = Math.min(((Math.floor((pa + 1) / 10) + 1) * 10), 9990)
        while (d <= 9999) {
          if (!used.has(d)) return d
          d += 10
        }
        // Último recurso: siguiente libre
        for (let c = pa + 1; c <= 9999; c++) if (!used.has(c)) return c
        return 9999
      }
      if (!used.has(cand)) return cand
      // Si está ocupada, buscar siguiente decena
      let d = Math.min(((Math.floor((cand + 1) / 10) * 10)), 9990)
      while (d <= 9999) {
        if (!used.has(d)) return d
        d += 10
      }
      // Último recurso: siguiente libre
      for (let c = pa + 1; c <= 9999; c++) if (!used.has(c)) return c
      return 9999
    }

    // Caso primera tarjeta: insertar antes de la primera
    if (esPrimera || (ps != null && routes.indexOf(ps) === 0)) {
      // Ejemplo: si ps=20, buscar 10; si ps=10, buscar 05; si ps=05, buscar 03
      if (ps <= 100) {
        // Para números pequeños, usar mitad
        const mitad = Math.floor(ps / 2)
        if (mitad >= 1 && !used.has(mitad)) return mitad
        // Si no, buscar el número más pequeño disponible
        for (let c = 1; c < ps; c++) if (!used.has(c)) return c
        return 1
      } else {
        // Para números grandes, buscar centena anterior
        let cand = Math.floor((ps - 1) / 100) * 100
        if (cand < 100) cand = 100
        if (!used.has(cand)) return cand
        // Si está ocupada, buscar decena anterior
        let d = Math.floor((ps - 1) / 10) * 10
        while (d >= 100) {
          if (!used.has(d)) return d
          d -= 10
        }
        // Último recurso: mitad
        const mid = Math.floor(ps / 2)
        if (mid >= 100 && !used.has(mid)) return mid
        for (let c = 100; c < ps; c++) if (!used.has(c)) return c
        return 100
      }
    }

    // Caso genérico: solo pa (última tarjeta seleccionada)
    if (pa != null) {
      const siguientes = routes.filter(r => r > pa)
      if (siguientes.length) {
        const prox = siguientes[0]
        if (prox - pa > 1) {
          const mitad = Math.floor((pa + prox) / 2)
          if (mitad > pa && mitad < prox && !used.has(mitad)) return mitad
          // Si la mitad está ocupada, probar uno abajo o uno arriba
          if (mitad - 1 > pa && !used.has(mitad - 1)) return mitad - 1
          if (mitad + 1 < prox && !used.has(mitad + 1)) return mitad + 1
        }
        // Si no cabe en el medio, buscar siguiente centena
        let cand = Math.min(((Math.floor(prox / 100) + 1) * 100), 9900)
        if (!used.has(cand)) return cand
        let d = Math.min(((Math.floor((cand + 1) / 10) * 10)), 9990)
        while (d <= 9999) {
          if (!used.has(d)) return d
          d += 10
        }
        for (let c = prox + 1; c <= 9999; c++) if (!used.has(c)) return c
        return 9999
      } else {
        // Último elemento: buscar siguiente centena mayor que pa
        let cand = Math.min(((Math.floor(pa / 100) + 1) * 100), 9900)
        if (cand === pa) {
          // Si pa ya es una centena (ej: 9900), buscar siguiente decena
          let d = Math.min(((Math.floor((pa + 1) / 10) + 1) * 10), 9990)
          while (d <= 9999) {
            if (!used.has(d)) return d
            d += 10
          }
          for (let c = pa + 1; c <= 9999; c++) if (!used.has(c)) return c
          return 9999
        }
        if (!used.has(cand)) return cand
        let d = Math.min(((Math.floor((cand + 1) / 10) * 10)), 9990)
        while (d <= 9999) {
          if (!used.has(d)) return d
          d += 10
        }
        for (let c = pa + 1; c <= 9999; c++) if (!used.has(c)) return c
        return 9999
      }
    }

    // Caso genérico: solo ps (primera tarjeta seleccionada)
    if (ps != null) {
      const anteriores = routes.filter(r => r < ps)
      if (anteriores.length) {
        const pa2 = anteriores[anteriores.length - 1]
        if (ps - pa2 > 1) {
          const mitad = Math.floor((pa2 + ps) / 2)
          if (mitad > pa2 && mitad < ps && !used.has(mitad)) return mitad
          // Si la mitad está ocupada, probar uno abajo o uno arriba
          if (mitad - 1 > pa2 && !used.has(mitad - 1)) return mitad - 1
          if (mitad + 1 < ps && !used.has(mitad + 1)) return mitad + 1
        }
        // Si no cabe en el medio, buscar centena anterior
        let cand = Math.floor((ps - 1) / 100) * 100
        if (cand < 100) cand = 100
        if (!used.has(cand)) return cand
        let d = Math.floor((ps - 1) / 10) * 10
        while (d >= 100) {
          if (!used.has(d)) return d
          d -= 10
        }
        const mid = Math.floor(ps / 2)
        if (mid >= 100 && !used.has(mid)) return mid
        for (let c = 100; c < ps; c++) if (!used.has(c)) return c
        return 100
      } else {
        // No hay anteriores: insertar antes de ps
        if (ps <= 100) {
          const mitad = Math.floor(ps / 2)
          if (mitad >= 1 && !used.has(mitad)) return mitad
          for (let c = 1; c < ps; c++) if (!used.has(c)) return c
          return 1
        } else {
          let cand = Math.floor((ps - 1) / 100) * 100
          if (cand < 100) cand = 100
          if (!used.has(cand)) return cand
          let d = Math.floor((ps - 1) / 10) * 10
          while (d >= 100) {
            if (!used.has(d)) return d
            d -= 10
          }
          const mid = Math.floor(ps / 2)
          if (mid >= 100 && !used.has(mid)) return mid
          for (let c = 100; c < ps; c++) if (!used.has(c)) return c
          return 100
        }
      }
    }

    // Sin contexto: ampliar por centena
    const maxR = routes[routes.length - 1]
    let cand = Math.min(((Math.floor(maxR / 100) + 1) * 100), 9900)
    if (!used.has(cand)) return cand
    let d = Math.min(((Math.floor((cand + 1) / 10) * 10)), 9990)
    while (d <= 9999) {
      if (!used.has(d)) return d
      d += 10
    }
    for (let c = maxR + 1; c <= 9999; c++) if (!used.has(c)) return c
    return 9900
  } catch {
    return 100
  }
}


