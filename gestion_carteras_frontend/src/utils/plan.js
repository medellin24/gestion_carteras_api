const STORAGE_KEYS = {
  remaining: 'plan_days_remaining',
  max: 'plan_max_days',
  updatedAt: 'plan_days_updated_at',
}

const DEFAULT_MAX_DAYS = 30

function parseNumber(value, fallback = null) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function dispatchPlanEvent() {
  try {
    window.dispatchEvent(new Event('plan-info-updated'))
  } catch {}
}

export function readPlanInfo() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return { remaining: null, max: DEFAULT_MAX_DAYS, updatedAt: null }
  }
  const remaining = parseNumber(window.localStorage.getItem(STORAGE_KEYS.remaining), null)
  const storedMax = parseNumber(window.localStorage.getItem(STORAGE_KEYS.max), null)
  const updatedAt = window.localStorage.getItem(STORAGE_KEYS.updatedAt) || null
  const remainingClamped = remaining != null ? Math.max(0, remaining) : null
  let max = storedMax
  if (max == null) {
    max = remainingClamped != null ? remainingClamped : DEFAULT_MAX_DAYS
  }
  if (remainingClamped != null) {
    max = Math.max(max, remainingClamped)
  }
  return { remaining: remainingClamped, max, updatedAt }
}

export function persistPlanInfoFromLimits(limits = {}) {
  if (typeof window === 'undefined' || !window.localStorage) {
    const remaining = parseNumber(limits?.days_remaining ?? limits?.daysRemaining, null)
    const remainingClamped = remaining != null ? Math.max(0, remaining) : null
    return {
      remaining: remainingClamped,
      max: remainingClamped != null ? Math.max(remainingClamped, DEFAULT_MAX_DAYS) : DEFAULT_MAX_DAYS,
      updatedAt: null,
    }
  }
  const remainingRaw = parseNumber(limits?.days_remaining ?? limits?.daysRemaining, null)
  const remaining = remainingRaw != null ? Math.max(0, remainingRaw) : null
  const prevMax = parseNumber(window.localStorage.getItem(STORAGE_KEYS.max), null)
  const candidates = []
  if (prevMax != null) candidates.push(prevMax)
  if (remaining != null) candidates.push(remaining)
  if (!candidates.length) candidates.push(DEFAULT_MAX_DAYS)
  const observedMax = candidates.reduce((acc, val) => (val > acc ? val : acc), candidates[0] || DEFAULT_MAX_DAYS)
  if (remaining != null) {
    window.localStorage.setItem(STORAGE_KEYS.remaining, String(remaining))
  }
  window.localStorage.setItem(STORAGE_KEYS.max, String(observedMax || DEFAULT_MAX_DAYS))
  const nowIso = new Date().toISOString()
  window.localStorage.setItem(STORAGE_KEYS.updatedAt, nowIso)
  dispatchPlanEvent()
  return { remaining, max: observedMax || DEFAULT_MAX_DAYS, updatedAt: nowIso }
}


