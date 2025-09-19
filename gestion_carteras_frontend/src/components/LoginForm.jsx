import React, { useState } from 'react'
import { apiClient } from '../api/client.js'
import { decodeJwtPayload } from '../utils/jwt.js'
import { Eye, EyeOff } from 'lucide-react'

function LoginForm({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!navigator.onLine) {
      setError('Sin conexión. Conéctate para iniciar sesión.')
      return
    }
    setIsLoading(true)
    try {
      const { access_token, refresh_token, role } = await apiClient.login({ username, password })
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      localStorage.setItem('user_role', role)
      localStorage.setItem('username', username)
      try {
        const payload = decodeJwtPayload(access_token)
        if (payload?.empleado_identificacion) {
          localStorage.setItem('empleado_identificacion', String(payload.empleado_identificacion))
        }
      } catch {}
      onSuccess?.(role)
    } catch (err) {
      setError(err?.message || 'Error al iniciar sesión')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>Iniciar sesión</h2>
      <label>
        Usuario
        <input
          type="text"
          inputMode="email"
          autoCapitalize="none"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="correo o usuario"
          required
        />
      </label>
      <label>
        Contraseña
        <div style={{position: 'relative'}}>
          <input
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            style={{paddingRight: '40px'}}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            style={{
              position: 'absolute',
              right: '8px',
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'none',
              border: 'none',
              color: 'var(--muted)',
              cursor: 'pointer',
              padding: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            title={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </label>
      {error && <div className="error" role="alert">{error}</div>}
      <button type="submit" disabled={isLoading} className="primary">
        {isLoading ? 'Entrando…' : 'Entrar'}
      </button>
    </form>
  )
}

export default LoginForm


