import React from 'react'

export default function DataCreditoGauge({ score }) {
  // Score 0 a 100
  // Colores: 
  // 80-100: Verde (#22c55e)
  // 60-79: Amarillo (#eab308)
  // 40-59: Naranja (#f97316)
  // 0-39: Rojo (#ef4444)

  let color = '#ef4444'
  let label = 'Riesgo Alto'
  if (score >= 80) {
    color = '#22c55e'
    label = 'Excelente'
  } else if (score >= 60) {
    color = '#eab308'
    label = 'Aceptable'
  } else if (score >= 40) {
    color = '#f97316'
    label = 'Regular'
  }

  // Calcular rotación para un semi-círculo (180 grados)
  // 0 -> -90deg, 100 -> 90deg
  const rotation = (score / 100) * 180 - 90

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '20px 0' }}>
      <div style={{ position: 'relative', width: 200, height: 100, overflow: 'hidden' }}>
        {/* Fondo gris */}
        <div style={{
          position: 'absolute',
          top: 0, left: 0,
          width: 200, height: 200,
          borderRadius: '50%',
          border: '20px solid #e5e7eb',
          boxSizing: 'border-box'
        }} />
        
        {/* Barra de progreso */}
        <div style={{
          position: 'absolute',
          top: 0, left: 0,
          width: 200, height: 200,
          borderRadius: '50%',
          border: `20px solid ${color}`,
          borderBottomColor: 'transparent',
          borderRightColor: 'transparent',
          boxSizing: 'border-box',
          transform: `rotate(${rotation}deg)`,
          transformOrigin: 'center',
          transition: 'transform 1s ease-out'
        }} />

        {/* Texto central */}
        <div style={{
          position: 'absolute',
          bottom: 0, left: 0, right: 0,
          textAlign: 'center',
          lineHeight: '1'
        }}>
          <span style={{ fontSize: 48, fontWeight: 'bold', color: '#374151' }}>{score}</span>
        </div>
      </div>
      <div style={{ marginTop: 10, fontSize: 18, fontWeight: '600', color }}>
        {label}
      </div>
    </div>
  )
}

