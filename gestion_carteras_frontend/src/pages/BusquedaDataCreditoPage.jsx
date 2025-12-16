import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Search } from 'lucide-react'

export default function BusquedaDataCreditoPage() {
  const [cedula, setCedula] = useState('')
  const navigate = useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault()
    if (cedula.trim()) {
      navigate(`/datacredito/${cedula.trim()}`)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-content">
          <button onClick={() => navigate(-1)} className="back-btn">
            <ArrowLeft size={24} />
          </button>
          <h1>Consultar Historial</h1>
        </div>
      </header>
      <main className="p-4">
        <div className="card">
          <h2 className="text-lg font-bold mb-4">Buscar Cliente</h2>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Número de Identificación
              </label>
              <input
                type="tel"
                value={cedula}
                onChange={(e) => setCedula(e.target.value)}
                placeholder="Ej: 1002345678"
                className="w-full p-3 border border-gray-300 rounded text-lg"
                autoFocus
              />
            </div>
            <button
              type="submit"
              disabled={!cedula.trim()}
              className="bg-blue-600 text-white py-3 px-4 rounded font-bold text-lg shadow hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2"
            >
              <Search size={20} />
              Consultar
            </button>
          </form>
        </div>
        
        <div className="mt-6 text-center text-gray-500 text-sm">
          <p>Ingrese la cédula del cliente para ver su hoja de vida crediticia, score y comportamiento de pago.</p>
        </div>
      </main>
    </div>
  )
}

