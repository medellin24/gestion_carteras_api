export function decodeJwtPayload(token) {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length !== 3) return null
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''))
    return JSON.parse(json)
  } catch {
    return null
  }
}

export function getCurrentRoleAndEmpleado() {
  const token = localStorage.getItem('access_token')
  const payload = decodeJwtPayload(token)
  const role = localStorage.getItem('user_role') || payload?.role || null
  const rawEmpleadoId = localStorage.getItem('empleado_identificacion') || payload?.empleado_identificacion || null
  const empleadoId = rawEmpleadoId ? String(rawEmpleadoId).substring(0, 20) : null
  return { role, empleadoId }
}
