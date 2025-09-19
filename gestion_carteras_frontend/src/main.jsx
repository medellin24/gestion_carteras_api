import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { BrowserRouter } from 'react-router-dom'
import './styles.css'
import { registerSW } from 'virtual:pwa-register'

// Aviso de actualización del SW
const updateSW = registerSW({
  immediate: true,
  onNeedRefresh() {
    try {
      const ok = window.confirm('Nueva versión disponible. ¿Actualizar ahora?')
      if (ok) updateSW(true)
    } catch {
      // fallback: intentar activar igualmente
      try { updateSW(true) } catch {}
    }
  },
  onOfflineReady() {
    // opcional: mostrar toast/log
    console.log('PWA lista para uso sin conexión')
  }
})

// Detectar si está instalada (standalone) y ajustar altura usable
function applyStandaloneViewportFix() {
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true
  if (isStandalone) {
    document.documentElement.classList.add('standalone')
  }
  const setAppDvh = () => {
    const appDvh = window.innerHeight
    document.documentElement.style.setProperty('--app-dvh', `${appDvh}px`)
  }
  setAppDvh()
  window.addEventListener('resize', setAppDvh)
}

applyStandaloneViewportFix()

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)


