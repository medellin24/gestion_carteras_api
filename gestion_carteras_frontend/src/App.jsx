import React, { useEffect, useState } from 'react'
import { Routes, Route, useNavigate, Navigate, Link, useLocation } from 'react-router-dom'
import LoginForm from './components/LoginForm.jsx'
import { Download, FolderOpenDot, Wallet, Upload, LogOut, Settings } from 'lucide-react'
import DescargarPage from './pages/Descargar.jsx'
import TarjetasPage from './pages/Tarjetas.jsx'
import TarjetaDetallePage from './pages/TarjetaDetalle.jsx'
import AbonosListadoPage from './pages/AbonosListado.jsx'
import SubirPage from './pages/Subir.jsx'
import GastosBasePage from './pages/GastosBase.jsx'
import { apiClient } from './api/client.js'
import { formatDateYYYYMMDD } from './utils/date.js'
import { readPlanInfo, persistPlanInfoFromLimits } from './utils/plan.js'

function Home() {
  const role = localStorage.getItem('user_role')
  const username = localStorage.getItem('username') || 'Usuario'
  const [flash, setFlash] = useState('')
  const [selectedEmployee, setSelectedEmployee] = useState(null)
  const [today, setToday] = useState(() => new Date())
  const [planInfo, setPlanInfo] = useState(() => readPlanInfo())
  
  useEffect(() => {
    const msg = localStorage.getItem('flash_message')
    if (msg) {
      setFlash(msg)
      localStorage.removeItem('flash_message')
      const t = setTimeout(() => setFlash(''), 4000)
      return () => clearTimeout(t)
    }
  }, [])

  useEffect(() => {
    const timer = setInterval(() => setToday(new Date()), 60_000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const handlePlanUpdate = () => setPlanInfo(readPlanInfo())
    const handleStorage = (event) => {
      if (!event || !event.key) return
      if (['plan_days_remaining', 'plan_max_days', 'plan_days_updated_at'].includes(event.key)) {
        handlePlanUpdate()
      }
    }
    window.addEventListener('plan-info-updated', handlePlanUpdate)
    window.addEventListener('storage', handleStorage)
    return () => {
      window.removeEventListener('plan-info-updated', handlePlanUpdate)
      window.removeEventListener('storage', handleStorage)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    apiClient.getLimits()
      .then((limits) => {
        if (cancelled) return
        const snapshot = persistPlanInfoFromLimits(limits)
        setPlanInfo(snapshot)
      })
      .catch(() => {
        if (!cancelled) {
          setPlanInfo(readPlanInfo())
        }
      })
    return () => { cancelled = true }
  }, [role])
  
  useEffect(() => {
    // Función para actualizar información del empleado
    const updateSelectedEmployee = () => {
      const empleadoId = localStorage.getItem('empleado_identificacion')
      if (role === 'admin' && empleadoId) {
        // Obtener el nombre del empleado desde localStorage
        const empleadoNombre = localStorage.getItem('empleado_nombre') || empleadoId
        setSelectedEmployee({ identificacion: empleadoId, nombre: empleadoNombre })
      } else {
        setSelectedEmployee(null)
      }
    }
    
    // Actualizar inicialmente
    updateSelectedEmployee()
    
    // Escuchar cambios en localStorage (cuando se selecciona un empleado)
    const handleStorageChange = (e) => {
      if (e.key === 'empleado_identificacion' || e.key === 'empleado_nombre') {
        updateSelectedEmployee()
      }
    }
    
    window.addEventListener('storage', handleStorageChange)
    
    // También escuchar eventos personalizados para cambios en la misma ventana
    const handleEmployeeChange = () => {
      updateSelectedEmployee()
    }
    
    window.addEventListener('empleado-selected', handleEmployeeChange)
    
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('empleado-selected', handleEmployeeChange)
    }
  }, [role])
  return (
    <div className="app-shell" style={{ overscrollBehaviorY: 'auto' }}>
      <header className="app-header home-header">
        <div className="home-header-top">
          <h1>Inicio</h1>
          <span className="badge">{role === 'admin' ? 'Admin' : 'Cobrador'}</span>
        </div>
        <div className="home-header-info">
          <span className="home-date-pill">Hoy: <strong>{formatDateYYYYMMDD(today)}</strong></span>
          <span className="home-plan-pill">
            Plan: quedan <strong>[{planInfo?.remaining != null ? planInfo.remaining : '—'}{planInfo?.max ? ` de ${planInfo.max}` : ''} días]</strong>
          </span>
        </div>
      </header>
      <main>
        {flash && (
          <div className="card" style={{maxWidth: 680}}>{flash}</div>
        )}
        <div className="card" style={{maxWidth: 680}}>
          <strong>Bienvenido, {username}</strong>
          <span style={{color:'var(--muted)'}}>Rol: {role}</span>
          {selectedEmployee && (
            <span style={{color:'var(--muted)', fontSize:14}}>Empleado seleccionado: {selectedEmployee.nombre}</span>
          )}
        </div>
        <nav className="tiles">
          <Link className="tile" to="/descargar"><Download style={{marginRight:8}} size={20}/> Descargar tarjetas</Link>
          <Link className="tile" to="/tarjetas"><FolderOpenDot style={{marginRight:8}} size={20}/> Ver tarjetas</Link>
          <Link className="tile" to="/gastos"><Wallet style={{marginRight:8}} size={20}/> Gastos y base</Link>
          <Link className="tile" to="/subir"><Upload style={{marginRight:8}} size={20}/> Subir tarjetas</Link>
          <Link className="tile" to="/logout"><LogOut style={{marginRight:8}} size={20}/> Cerrar sesión</Link>
          <Link className="tile" to="/opciones"><Settings style={{marginRight:8}} size={20}/> Opciones</Link>
        </nav>
      </main>
    </div>
  )
}

function Logout() {
  useEffect(() => {
    localStorage.clear()
    location.href = '/'
  }, [])
  return null
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [userRole, setUserRole] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    const role = localStorage.getItem('user_role')
    if (token) {
      setIsAuthenticated(true)
      setUserRole(role)
      // Si ya está logueado, ir a Home
      navigate('/home', { replace: true })
    }
  }, [])

  // Alternar clase para permitir pull-to-refresh sólo en / y /home (si quieres sólo /, deja solo '/')
  useEffect(() => {
    const path = location.pathname
    const allow = path === '/' || path === '/home'
    const el = document.documentElement
    const body = document.body
    if (allow) {
      el.classList.add('allow-ptr')
      body.classList.add('allow-ptr')
    } else {
      el.classList.remove('allow-ptr')
      body.classList.remove('allow-ptr')
    }
  }, [location.pathname])

  // Asegurar nombre del empleado para cobrador
  useEffect(() => {
    const role = localStorage.getItem('user_role')
    const empId = localStorage.getItem('empleado_identificacion')
    if (role === 'cobrador' && empId) {
      const existingName = localStorage.getItem('empleado_nombre')
      if (!existingName || existingName === empId) {
        // Intentar poblar desde tarjetas cacheadas
        try {
          const raw = localStorage.getItem('tarjetas_data')
          if (raw) {
            const arr = JSON.parse(raw)
            const first = Array.isArray(arr) ? arr.find(t => t?.empleado_identificacion === empId) : null
            const nombre = first?.empleado_nombre || null
            if (nombre) {
              localStorage.setItem('empleado_nombre', nombre)
              window.dispatchEvent(new Event('empleado-selected'))
            }
          }
        } catch {}
      }
    }
  }, [])

  return (
    <Routes>
      <Route path="/" element={
        <div className="app-shell" style={{ overscrollBehaviorY: 'auto' }}>
          <header className="app-header"><h1>Gestión de Carteras</h1></header>
          <main>
            <LoginForm onSuccess={(role) => { setIsAuthenticated(true); setUserRole(role); navigate('/home') }} />
          </main>
        </div>
      } />
      <Route path="/home" element={isAuthenticated ? <Home /> : <Navigate to="/" replace />} />
      <Route path="/descargar" element={isAuthenticated ? <DescargarPage /> : <Navigate to="/" replace />} />
      <Route path="/tarjetas" element={isAuthenticated ? <TarjetasPage /> : <Navigate to="/" replace />}>
        <Route path=":codigo" element={<TarjetaDetallePage />} />
        <Route path=":codigo/abonos" element={<AbonosListadoPage />} />
      </Route>
      <Route path="/gastos" element={isAuthenticated ? <GastosBasePage /> : <Navigate to="/" replace />} />
      <Route path="/subir" element={isAuthenticated ? <SubirPage /> : <Navigate to="/" replace />} />
      <Route path="/opciones" element={isAuthenticated ? <div className="app-shell"><header className="app-header"><h1>Opciones</h1></header><main><p>Placeholder opciones.</p></main></div> : <Navigate to="/" replace />} />
      <Route path="/logout" element={<Logout />} />
    </Routes>
  )
}

export default App


