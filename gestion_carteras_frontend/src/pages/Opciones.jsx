import React, { useState } from 'react'
import { CheckCircle2, LayoutList, LayoutGrid } from 'lucide-react'
import { tarjetasStore } from '../state/store.js'

export default function OpcionesPage() {
  const [viewMode, setViewMode] = useState(() => tarjetasStore.getViewMode())

  const handleModeChange = (mode) => {
    tarjetasStore.setViewMode(mode)
    setViewMode(mode)
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Opciones</h1>
      </header>
      <main style={{ padding: 16 }}>
        <section style={{ marginBottom: 24 }}>
          <h2 className="neon-title" style={{ marginBottom: 12 }}>Modo de Visualización</h2>
          <div style={{ display: 'grid', gap: 12 }}>
            <button 
              onClick={() => handleModeChange('cards')}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: 16,
                background: viewMode === 'cards' ? 'rgba(59,130,246,0.1)' : '#0e1526',
                border: `1px solid ${viewMode === 'cards' ? '#3b82f6' : '#1f2a44'}`,
                borderRadius: 12,
                color: '#fff',
                cursor: 'pointer',
                textAlign: 'left'
              }}
            >
              <LayoutGrid size={24} color={viewMode === 'cards' ? '#3b82f6' : '#888'} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>Tarjetas (Detallado)</div>
                <div style={{ fontSize: 13, color: '#888', marginTop: 2 }}>
                  Vista completa con gestos y detalles
                </div>
              </div>
              {viewMode === 'cards' && <CheckCircle2 size={20} color="#3b82f6" />}
            </button>

            <button 
              onClick={() => handleModeChange('list')}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: 16,
                background: viewMode === 'list' ? 'rgba(16,185,129,0.1)' : '#0e1526',
                border: `1px solid ${viewMode === 'list' ? '#10b981' : '#1f2a44'}`,
                borderRadius: 12,
                color: '#fff',
                cursor: 'pointer',
                textAlign: 'left'
              }}
            >
              <LayoutList size={24} color={viewMode === 'list' ? '#10b981' : '#888'} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>Lista Rápida (Compacto)</div>
                <div style={{ fontSize: 13, color: '#888', marginTop: 2 }}>
                  Filas simples para cobro veloz
                </div>
              </div>
              {viewMode === 'list' && <CheckCircle2 size={20} color="#10b981" />}
            </button>
          </div>
        </section>
      </main>
    </div>
  )
}
