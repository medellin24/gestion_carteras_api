import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
// API deshabilitada en listado para evitar llamadas post-descarga
import { offlineDB } from '../offline/db.js'
import { parseISODateToLocal, formatDateYYYYMMDD } from '../utils/date.js'

export default function AbonosListadoPage(){
  const { codigo } = useParams()
  const [abonos, setAbonos] = useState([])
  const [error, setError] = useState('')

  useEffect(()=>{
    async function load(){
      try{
        const local = await offlineDB.getAbonos(codigo)
        if (local && local.length) setAbonos(local)
        // No se realizan llamadas a la API aquí; se usa únicamente IndexedDB
      }catch(e){ setError(e?.message||'Error cargando abonos') }
    }
    load()
  },[codigo])

  return (
    <div className="app-shell">
      <header className="app-header"><h1>Abonos</h1></header>
      <main>
        {error && <div className="error">{error}</div>}
        <div className="card" style={{maxWidth:680}}>
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Fecha</th>
                <th>Monto</th>
              </tr>
            </thead>
            <tbody>
              {abonos.length === 0 && (
                <tr><td colSpan="3">No hay abonos.</td></tr>
              )}
              {[...abonos]
                .sort((a, b) => {
                  // Ordenar del más antiguo al más reciente
                  const fechaA = a?.fecha ? parseISODateToLocal(String(a.fecha)) : new Date(a.ts || 0)
                  const fechaB = b?.fecha ? parseISODateToLocal(String(b.fecha)) : new Date(b.ts || 0)
                  return fechaA - fechaB
                })
                .map((a, idx)=> (
                <tr key={a.id||idx}>
                  <td>{idx+1}</td>
                  <td className="val-date">
                    {(() => {
                      const d = a?.fecha ? parseISODateToLocal(String(a.fecha)) : (a?.ts ? new Date(a.ts) : null)
                      return d ? formatDateYYYYMMDD(d) : '—'
                    })()}
                  </td>
                  <td className="val-pos">{Number(a.monto).toLocaleString('es-CO')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}
