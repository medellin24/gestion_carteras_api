import React, { useState, useEffect } from 'react'
import { offlineDB } from '../offline/db.js'
import { getCurrentRoleAndEmpleado } from '../utils/jwt.js'
import { getLocalDateString } from '../utils/date.js'

export default function GastosBasePage(){
  const [tipo, setTipo] = useState('GASOLINA')
  const [valor, setValor] = useState('')
  const [observacion, setObservacion] = useState('')
  const [base, setBase] = useState('')
  const [gastoMessage, setGastoMessage] = useState('')
  const [gastoMessageType, setGastoMessageType] = useState('info') // 'success', 'error', 'info'
  const [baseMessage, setBaseMessage] = useState('')
  const [baseMessageType, setBaseMessageType] = useState('info') // 'success', 'error', 'info'
  const [existingBase, setExistingBase] = useState(null)
  const [busy, setBusy] = useState(false)

  const [{ empleadoId }] = useState(getCurrentRoleAndEmpleado())

  useEffect(() => {
    checkExistingBase()
  }, [])

  async function checkExistingBase() {
    try {
      const outbox = await offlineDB.readOutbox()
      const today = getLocalDateString()
      const baseToday = outbox.find(item => 
        item.type === 'base:set' && 
        item.fecha === today
      )
      if (baseToday) {
        setExistingBase(baseToday)
        setBase(String(baseToday.monto))
      }
    } catch (e) {
      console.error('Error checking existing base:', e)
    }
  }

  function playSound(type = 'success') {
    try {
      // Crear un sonido simple usando Web Audio API
      const audioContext = new (window.AudioContext || window.webkitAudioContext)()
      const oscillator = audioContext.createOscillator()
      const gainNode = audioContext.createGain()
      
      oscillator.connect(gainNode)
      gainNode.connect(audioContext.destination)
      
      if (type === 'success') {
        // Sonido de éxito: dos tonos ascendentes
        oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime) // C5
        oscillator.frequency.setValueAtTime(659.25, audioContext.currentTime + 0.1) // E5
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3)
        oscillator.start(audioContext.currentTime)
        oscillator.stop(audioContext.currentTime + 0.3)
      } else if (type === 'error') {
        // Sonido de error: tono descendente
        oscillator.frequency.setValueAtTime(400, audioContext.currentTime)
        oscillator.frequency.setValueAtTime(200, audioContext.currentTime + 0.2)
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.4)
        oscillator.start(audioContext.currentTime)
        oscillator.stop(audioContext.currentTime + 0.4)
      }
    } catch (e) {
      // Si no se puede reproducir sonido, no hacer nada
      console.log('No se pudo reproducir sonido:', e)
    }
  }

  function showGastoMessage(msg, type = 'info') {
    setGastoMessage(msg)
    setGastoMessageType(type)
    
    // Reproducir sonido según el tipo
    if (type === 'success') {
      playSound('success')
    } else if (type === 'error') {
      playSound('error')
    }
    
    setTimeout(() => setGastoMessage(''), 5000)
  }

  function showBaseMessage(msg, type = 'info') {
    setBaseMessage(msg)
    setBaseMessageType(type)
    
    // Reproducir sonido según el tipo
    if (type === 'success') {
      playSound('success')
    } else if (type === 'error') {
      playSound('error')
    }
    
    setTimeout(() => setBaseMessage(''), 5000)
  }

  async function addGasto(){
    setGastoMessage('')
    setBusy(true)
    
    try {
      const v = Number(String(valor).replace(/[^0-9.]/g,''))
      if (!Number.isFinite(v) || v <= 0) { 
        showGastoMessage('Valor de gasto inválido', 'error')
        return 
      }
      
      // Observación ahora es opcional

      const rawEmpleadoId = empleadoId || localStorage.getItem('empleado_identificacion')
      const empleado_identificacion = rawEmpleadoId ? String(rawEmpleadoId).substring(0, 20) : null
      if (!empleado_identificacion) {
        showGastoMessage('No se encontró empleado_identificacion en la sesión. Debes seleccionar un empleado primero.', 'error')
        return
      }

      await offlineDB.queueOperation({ 
        type:'gasto:new', 
        tipo, 
        valor: v, 
        observacion: observacion.trim(),
        fecha: getLocalDateString(), // Fecha local en formato YYYY-MM-DD
        empleado_identificacion,
        ts: Date.now() 
      })
      
      showGastoMessage('Gasto registrado exitosamente. Puedes visualizarlo en la consola de subida.', 'success')
      setValor('')
      setObservacion('')
    } catch (e) {
      showGastoMessage('Error al agregar gasto: ' + (e?.message || 'Error'), 'error')
    } finally {
      setBusy(false)
    }
  }

  async function setBaseDia(){
    setBaseMessage('')
    setBusy(true)
    
    try {
      const v = Number(String(base).replace(/[^0-9.]/g,''))
      if (!Number.isFinite(v) || v < 0) { 
        showBaseMessage('Base inválida', 'error')
        return 
      }

      const rawEmpleadoId = empleadoId || localStorage.getItem('empleado_identificacion')
      const empleado_id = rawEmpleadoId ? String(rawEmpleadoId).substring(0, 20) : null
      if (!empleado_id) {
        showBaseMessage('No se encontró empleado_identificacion en la sesión. Debes seleccionar un empleado primero.', 'error')
        return
      }

      // Si ya existe una base para hoy, eliminarla primero
      if (existingBase) {
        await offlineDB.removeOutbox(existingBase.id)
      }

      await offlineDB.queueOperation({ 
        type:'base:set', 
        fecha: getLocalDateString(), // Fecha local en formato YYYY-MM-DD 
        monto: v,
        empleado_id,
        ts: Date.now() 
      })
      
      showBaseMessage(existingBase ? 'Base actualizada exitosamente. Puedes visualizarla en la consola de subida.' : 'Base registrada exitosamente. Puedes visualizarla en la consola de subida.', 'success')
      await checkExistingBase()
    } catch (e) {
      showBaseMessage('Error al registrar base: ' + (e?.message || 'Error'), 'error')
    } finally {
      setBusy(false)
    }
  }

  const currentEmpleadoId = localStorage.getItem('empleado_identificacion')
  const currentEmpleadoName = localStorage.getItem('empleado_nombre') || ''

  return (
    <div className="app-shell">
      <header className="app-header"><h1>Gastos y Base</h1></header>
      <main>
        {/* Indicador de empleado actual */}
        {currentEmpleadoId && (
          <div className="card" style={{maxWidth:680, background:'#1e3a8a', color:'white'}}>
            <strong>Empleado actual: {currentEmpleadoName || currentEmpleadoId}</strong>
            <span style={{color:'#93c5fd', fontSize:14}}>Los gastos y bases se registrarán para este empleado</span>
          </div>
        )}
        
        {!currentEmpleadoId && (
          <div className="card" style={{maxWidth:680, background:'#7f1d1d', color:'white'}}>
            <strong>⚠️ No hay empleado seleccionado</strong>
            <span style={{color:'#fca5a5', fontSize:14}}>Debes seleccionar un empleado primero para registrar gastos y bases</span>
          </div>
        )}

        <div className="card" style={{maxWidth:680, display:'grid', gap:8}}>
          <strong>Agregar gasto</strong>
          <label>Tipo
            <select value={tipo} onChange={(e)=>setTipo(e.target.value)} disabled={busy}>
              <option>GASOLINA</option>
              <option>VIATICOS</option>
              <option>MANTENIMIENTO</option>
              <option>SALARIO</option>
              <option>OTROS</option>
            </select>
          </label>
          <label>Valor
            <input 
              value={valor} 
              onChange={(e)=>setValor(e.target.value)} 
              placeholder="0" 
              disabled={busy}
            />
          </label>
          <label>Observación
            <input 
              value={observacion} 
              onChange={(e)=>setObservacion(e.target.value)} 
              placeholder="Descripción del gasto (opcional)" 
              disabled={busy}
            />
          </label>
          {gastoMessage && (
            <div style={{
              padding:8, 
              background: gastoMessageType === 'success' ? '#14532d' : gastoMessageType === 'error' ? '#7f1d1d' : '#1e3a8a',
              color: 'white',
              borderRadius: 4,
              fontSize: 14
            }}>
              {gastoMessage}
            </div>
          )}
          <button className="primary" onClick={addGasto} disabled={busy}>
            {busy ? 'Agregando...' : 'Agregar gasto'}
          </button>
        </div>

        <div className="card" style={{maxWidth:680, display:'grid', gap:8}}>
          <strong>Base del día</strong>
          {existingBase && (
            <div style={{padding:8, background:'#1e3a8a', color:'white', borderRadius:4, fontSize:14}}>
              Ya tienes una base registrada para hoy: ${existingBase.monto?.toLocaleString()}
            </div>
          )}
          <label>Monto
            <input 
              value={base} 
              onChange={(e)=>setBase(e.target.value)} 
              placeholder="0" 
              disabled={busy}
            />
          </label>
          {baseMessage && (
            <div style={{
              padding:8, 
              background: baseMessageType === 'success' ? '#14532d' : baseMessageType === 'error' ? '#7f1d1d' : '#1e3a8a',
              color: 'white',
              borderRadius: 4,
              fontSize: 14
            }}>
              {baseMessage}
            </div>
          )}
          <button onClick={setBaseDia} disabled={busy}>
            {busy ? 'Registrando...' : (existingBase ? 'Actualizar base' : 'Registrar base')}
          </button>
          <div style={{fontSize:12, color:'var(--muted)'}}>
            * Solo puede haber una base por empleado por día
          </div>
        </div>
      </main>
    </div>
  )
}


