import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, TrendingUp, Clock, AlertCircle, CheckCircle, XCircle } from 'lucide-react'
import { apiClient } from '../api/client'

// Estilos inline para el tema oscuro moderno
const styles = {
  page: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #0f0c29 0%, #1a1a2e 50%, #16213e 100%)',
    color: '#fff',
    fontFamily: "'Inter', 'SF Pro Display', -apple-system, sans-serif",
  },
  header: {
    background: 'rgba(255,255,255,0.03)',
    backdropFilter: 'blur(20px)',
    borderBottom: '1px solid rgba(255,255,255,0.08)',
    padding: '16px 20px',
    position: 'sticky',
    top: 0,
    zIndex: 100,
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  backBtn: {
    background: 'rgba(255,255,255,0.1)',
    border: 'none',
    borderRadius: '12px',
    padding: '10px',
    color: '#fff',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.2s',
  },
  title: {
    fontSize: '18px',
    fontWeight: '700',
    letterSpacing: '-0.3px',
    background: 'linear-gradient(90deg, #fff 0%, #a78bfa 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  content: {
    padding: '20px',
    maxWidth: '600px',
    margin: '0 auto',
  },
  // Tarjeta de cliente
  clientCard: {
    background: 'linear-gradient(135deg, rgba(167,139,250,0.15) 0%, rgba(139,92,246,0.08) 100%)',
    borderRadius: '20px',
    padding: '24px',
    marginBottom: '20px',
    border: '1px solid rgba(167,139,250,0.2)',
    position: 'relative',
    overflow: 'hidden',
  },
  clientCardGlow: {
    position: 'absolute',
    top: '-50%',
    right: '-30%',
    width: '200px',
    height: '200px',
    background: 'radial-gradient(circle, rgba(167,139,250,0.3) 0%, transparent 70%)',
    pointerEvents: 'none',
  },
  clientName: {
    fontSize: '28px',
    fontWeight: '800',
    letterSpacing: '-0.5px',
    marginBottom: '4px',
  },
  clientId: {
    fontSize: '14px',
    color: 'rgba(255,255,255,0.5)',
    fontFamily: 'monospace',
    letterSpacing: '1px',
  },
  // Score Card
  scoreCard: {
    background: 'rgba(255,255,255,0.04)',
    borderRadius: '24px',
    padding: '28px',
    marginBottom: '20px',
    border: '1px solid rgba(255,255,255,0.06)',
    textAlign: 'center',
  },
  // Stats Grid
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
    marginTop: '20px',
  },
  statBox: {
    background: 'rgba(255,255,255,0.04)',
    borderRadius: '16px',
    padding: '16px',
    border: '1px solid rgba(255,255,255,0.06)',
  },
  statValue: {
    fontSize: '28px',
    fontWeight: '800',
    letterSpacing: '-1px',
  },
  statLabel: {
    fontSize: '11px',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    color: 'rgba(255,255,255,0.4)',
    marginTop: '4px',
  },
  // Sección
  section: {
    marginTop: '32px',
  },
  sectionTitle: {
    fontSize: '13px',
    textTransform: 'uppercase',
    letterSpacing: '2px',
    color: 'rgba(255,255,255,0.4)',
    marginBottom: '16px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  // Crédito Card
  creditCard: {
    background: 'rgba(255,255,255,0.03)',
    borderRadius: '20px',
    padding: '20px',
    marginBottom: '14px',
    border: '1px solid rgba(255,255,255,0.06)',
    position: 'relative',
    overflow: 'hidden',
  },
  creditHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '16px',
  },
  creditAmount: {
    fontSize: '26px',
    fontWeight: '800',
    letterSpacing: '-0.5px',
  },
  creditDate: {
    fontSize: '12px',
    color: 'rgba(255,255,255,0.4)',
    marginTop: '4px',
  },
  creditScore: {
    textAlign: 'right',
  },
  creditScoreValue: {
    fontSize: '28px',
    fontWeight: '900',
    lineHeight: 1,
  },
  creditScoreLabel: {
    fontSize: '9px',
    textTransform: 'uppercase',
    letterSpacing: '1.5px',
    color: 'rgba(255,255,255,0.4)',
  },
  // Indicadores Grid
  indicatorsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '10px',
  },
  indicator: {
    background: 'rgba(0,0,0,0.2)',
    borderRadius: '12px',
    padding: '12px',
    position: 'relative',
  },
  indicatorLabel: {
    fontSize: '10px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    color: 'rgba(255,255,255,0.5)',
    marginBottom: '4px',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  indicatorValue: {
    fontSize: '20px',
    fontWeight: '700',
  },
  // Badge de estado y semáforo
  badgeRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
    gap: '8px',
  },
  badge: {
    padding: '4px 10px',
    borderRadius: '20px',
    fontSize: '10px',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    fontWeight: '600',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  semaforoBadge: {
    padding: '4px 12px',
    borderRadius: '20px',
    fontSize: '10px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    fontWeight: '700',
  },
  // Empty state
  emptyState: {
    textAlign: 'center',
    padding: '40px 20px',
    color: 'rgba(255,255,255,0.3)',
    border: '2px dashed rgba(255,255,255,0.1)',
    borderRadius: '20px',
    fontSize: '14px',
  },
  // Info button
  infoBtn: {
    background: 'none',
    border: 'none',
    padding: '2px',
    cursor: 'pointer',
    opacity: 0.5,
    transition: 'opacity 0.2s, transform 0.2s',
    display: 'inline-flex',
    alignItems: 'center',
  },
  // Empresa badge
  empresaBadge: {
    fontSize: '11px',
    color: 'rgba(255,255,255,0.4)',
    marginTop: '2px',
    fontStyle: 'italic',
  },
}

// Clasificación semáforo según lógica de frame_entrega
function getSemaforoClasificacion(puntaje_atraso_cierre) {
  const dias = Math.round(puntaje_atraso_cierre || 0)
  if (dias === 0) return { label: 'Excelente', bg: 'rgba(34,197,94,0.25)', color: '#22c55e' }
  if (dias <= 6) return { label: 'Bueno', bg: 'rgba(59,130,246,0.25)', color: '#3b82f6' }
  if (dias <= 15) return { label: 'Regular', bg: 'rgba(250,204,21,0.25)', color: '#facc15' }
  if (dias <= 60) return { label: 'Malo', bg: 'rgba(251,146,60,0.25)', color: '#fb923c' }
  return { label: 'Clavo', bg: 'rgba(239,68,68,0.25)', color: '#ef4444' }
}

// Función para determinar color según score
function getScoreColor(score) {
  if (score >= 80) return { bg: 'rgba(34,197,94,0.15)', border: 'rgba(34,197,94,0.3)', text: '#22c55e', gradient: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)' }
  if (score >= 60) return { bg: 'rgba(250,204,21,0.15)', border: 'rgba(250,204,21,0.3)', text: '#facc15', gradient: 'linear-gradient(135deg, #facc15 0%, #eab308 100%)' }
  if (score >= 40) return { bg: 'rgba(251,146,60,0.15)', border: 'rgba(251,146,60,0.3)', text: '#fb923c', gradient: 'linear-gradient(135deg, #fb923c 0%, #f97316 100%)' }
  return { bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.3)', text: '#ef4444', gradient: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)' }
}

function getStatusBadge(estado) {
  const s = String(estado).toLowerCase()
  if (s.includes('activa')) return { bg: 'rgba(34,197,94,0.2)', color: '#22c55e', icon: CheckCircle, label: 'Activa' }
  if (s.includes('pendiente')) return { bg: 'rgba(251,146,60,0.2)', color: '#fb923c', icon: Clock, label: 'Pendiente' }
  if (s.includes('cancelada')) return { bg: 'rgba(148,163,184,0.2)', color: '#94a3b8', icon: CheckCircle, label: 'Cancelada' }
  return { bg: 'rgba(239,68,68,0.2)', color: '#ef4444', icon: XCircle, label: estado }
}

// Generar nombre enmascarado de empresa
function getEmpresaEnmascarada(empresaAnonym, index) {
  if (!empresaAnonym || empresaAnonym === 'Esta Empresa') {
    return 'Tu Oficina'
  }
  // Para empresas externas, usar nombre genérico
  return `Oficina ${index + 1}`
}

// Componente Gauge con velocímetro/aguja
function GaugeChart({ score }) {
  const scoreColors = getScoreColor(score)
  
  // Calcular ángulo de la aguja (0 = izquierda, 180 = derecha)
  const angle = (score / 100) * 180 - 90 // -90 a 90 grados
  
  return (
    <div style={{ position: 'relative', width: '200px', height: '120px', margin: '-20px auto 0' }}>
      {/* Fondo del gauge */}
      <svg viewBox="0 0 200 110" style={{ width: '100%', height: '100%' }}>
        {/* Arco de fondo */}
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ef4444" />
            <stop offset="30%" stopColor="#fb923c" />
            <stop offset="50%" stopColor="#facc15" />
            <stop offset="70%" stopColor="#84cc16" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        
        {/* Arco de fondo gris */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        
        {/* Arco coloreado de progreso */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="url(#gaugeGradient)"
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * 251.2} 251.2`}
        />
        
        {/* Marcas */}
        {[0, 25, 50, 75, 100].map((mark, i) => {
          const markAngle = (mark / 100) * 180 - 180
          const rad = (markAngle * Math.PI) / 180
          const x1 = 100 + 65 * Math.cos(rad)
          const y1 = 100 + 65 * Math.sin(rad)
          const x2 = 100 + 75 * Math.cos(rad)
          const y2 = 100 + 75 * Math.sin(rad)
          return (
            <g key={i}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
              <text
                x={100 + 52 * Math.cos(rad)}
                y={100 + 52 * Math.sin(rad)}
                fill="rgba(255,255,255,0.4)"
                fontSize="10"
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {mark}
              </text>
            </g>
          )
        })}
        
        {/* Aguja */}
        <g transform={`rotate(${angle}, 100, 100)`} filter="url(#glow)">
          <polygon
            points="100,30 96,100 104,100"
            fill={scoreColors.text}
          />
          <circle cx="100" cy="100" r="8" fill={scoreColors.text} />
          <circle cx="100" cy="100" r="4" fill="#1a1a2e" />
        </g>
      </svg>
      
      {/* Valor del score */}
      <div style={{
        position: 'absolute',
        bottom: '-35px', // más abajo para evitar cualquier superposición (~0.5 cm aprox en móvil)
        left: '50%',
        transform: 'translateX(-50%)',
        textAlign: 'center',
      }}>
        <div style={{
          fontSize: '36px',
          fontWeight: '900',
          color: scoreColors.text,
          textShadow: `0 0 20px ${scoreColors.text}50`,
          lineHeight: 1,
        }}>
          {score}
        </div>
        <div style={{
          fontSize: '10px',
          textTransform: 'uppercase',
          letterSpacing: '2px',
          color: 'rgba(255,255,255,0.4)',
        }}>
          puntos
        </div>
      </div>
    </div>
  )
}

// Modal simple para mostrar tooltips
function showTooltip(title, message) {
  alert(`${title}\n\n${message}`)
}

export default function DataCreditoPage() {
  const { identificacion } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadReport()
  }, [identificacion])

  async function loadReport() {
    try {
      setLoading(true)
      const data = await apiClient.getDataCreditoReport(identificacion)
      setReport(data)
    } catch (err) {
      console.error(err)
      // Manejo amable para cliente sin historial (404)
      if (err?.status === 404 || /no encontrado/i.test(err?.message || '')) {
        setError('Este cliente no tiene historial crediticio aún.')
      } else {
        setError('No se pudo cargar el reporte de crédito.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{...styles.page, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <div style={{textAlign: 'center'}}>
          <div style={{
            width: '40px', height: '40px', border: '3px solid rgba(167,139,250,0.3)',
            borderTopColor: '#a78bfa', borderRadius: '50%', margin: '0 auto 16px',
            animation: 'spin 1s linear infinite'
          }}/>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <div style={{color: 'rgba(255,255,255,0.5)'}}>Cargando historial...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{...styles.page, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <div style={{textAlign: 'center', color: '#ef4444'}}>{error}</div>
      </div>
    )
  }

  if (!report) return null

  const scoreColors = getScoreColor(report.score_global)

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <button style={styles.backBtn} onClick={() => navigate(-1)}>
          <ArrowLeft size={20} />
        </button>
        <span style={styles.title}>Hoja de Vida Crediticia</span>
      </div>

      <div style={styles.content}>
        {/* Client Card */}
        <div style={styles.clientCard}>
          <div style={styles.clientCardGlow} />
          <div style={styles.clientName}>
            {report.cliente_nombre} {report.cliente_apellido}
          </div>
          <div style={styles.clientId}>
            CC {report.cliente_identificacion}
          </div>
        </div>

        {/* Score Card */}
        <div style={styles.scoreCard}>
          {/* Título del Score */}
          <div style={{
            fontSize: '12px',
            textTransform: 'uppercase',
            letterSpacing: '2px',
            color: 'rgba(255,255,255,0.5)',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
          }}>
            Score de Riesgo Crediticio
            <button 
              style={styles.infoBtn}
              onClick={() => showTooltip('Score de Riesgo', 'Puntaje de 0 a 100 que mide el comportamiento de pago histórico y actual. 100 = Cliente perfecto, 0 = Alto riesgo.')}
            >
              <AlertCircle size={14} color="rgba(255,255,255,0.5)" />
            </button>
          </div>
          
          {/* Gauge con velocímetro */}
          <GaugeChart score={report.score_global} />
          
          <div style={{fontSize: '14px', color: 'rgba(255,255,255,0.6)', marginTop: '56px', marginBottom: '8px'}}>
            {report.score_global >= 80 ? '🌟 Excelente historial crediticio' :
             report.score_global >= 60 ? '✅ Buen comportamiento de pago' :
             report.score_global >= 40 ? '⚠️ Historial con algunas alertas' :
             '🚨 Alto riesgo crediticio'}
          </div>

          {/* Stats */}
          <div style={{...styles.statsGrid, marginTop: '60px'}}>
            <div style={{...styles.statBox, background: 'rgba(34,197,94,0.1)', borderColor: 'rgba(34,197,94,0.2)'}}>
              <div style={{...styles.statValue, color: '#22c55e'}}>{report.total_creditos_activos}</div>
              <div style={styles.statLabel}>Activos</div>
            </div>
            <div style={styles.statBox}>
              <div style={styles.statValue}>{report.total_creditos_cerrados}</div>
              <div style={styles.statLabel}>Cerrados</div>
            </div>
            <div style={styles.statBox}>
              <div style={{...styles.statValue, color: report.promedio_retraso_historico > 3 ? '#ef4444' : '#22c55e'}}>
                {report.promedio_retraso_historico}d
              </div>
              <div style={{...styles.statLabel, display: 'flex', alignItems: 'center', gap: '4px'}}>
                Prom. Retraso
                <button 
                  style={{...styles.infoBtn, marginTop: 0}}
                  onClick={() => showTooltip('Promedio de Retraso', 'Días promedio de retraso en el cierre de sus créditos.')}
                >
                  <AlertCircle size={10} color="rgba(255,255,255,0.4)" />
                </button>
              </div>
            </div>
            <div style={styles.statBox}>
              <div style={{...styles.statValue, color: report.frecuencia_pago_promedio >= 70 ? '#22c55e' : '#fb923c'}}>
                {report.frecuencia_pago_promedio}%
              </div>
              <div style={{...styles.statLabel, display: 'flex', alignItems: 'center', gap: '4px'}}>
                Puntualidad
                <button 
                  style={{...styles.infoBtn, marginTop: 0}}
                  onClick={() => showTooltip('Puntualidad', 'Porcentaje de días que el cliente estuvo al día con sus pagos.')}
                >
                  <AlertCircle size={10} color="rgba(255,255,255,0.4)" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Lista de Préstamos (antes Créditos Activos) */}
        {report.tarjetas_activas && report.tarjetas_activas.length > 0 && (
          <div style={styles.section}>
            <div style={styles.sectionTitle}>
              <TrendingUp size={14} /> Lista de Préstamos
            </div>
            {report.tarjetas_activas.map((t, idx) => (
              <CreditCard key={idx} data={t} empresaIndex={idx} />
            ))}
          </div>
        )}

        {/* Historial */}
        <div style={styles.section}>
          <div style={styles.sectionTitle}>
            <Clock size={14} /> Historial Pasado
          </div>
          {report.historial_compactado && report.historial_compactado.length > 0 ? (
            report.historial_compactado.map((t, idx) => (
              <CreditCard key={idx} data={t} isHistory empresaIndex={idx} />
            ))
          ) : (
            <div style={styles.emptyState}>
              Sin historial archivado aún
            </div>
          )}
        </div>

      </div>
    </div>
  )
}

function CreditCard({ data, isHistory = false, empresaIndex = 0 }) {
  const scoreColors = getScoreColor(data.score_individual)
  const statusBadge = getStatusBadge(data.estado_final)
  const StatusIcon = statusBadge.icon
  const semaforo = getSemaforoClasificacion(data.puntaje_atraso_cierre)
  const empresaNombre = getEmpresaEnmascarada(data.empresa_anonym, empresaIndex)

  return (
    <div style={{
      ...styles.creditCard,
      borderLeft: `3px solid ${scoreColors.text}`,
      background: isHistory ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.04)',
    }}>
      {/* Fila de badges: Estado + Semáforo */}
      <div style={styles.badgeRow}>
        <div style={{
          ...styles.badge,
          background: statusBadge.bg,
          color: statusBadge.color,
        }}>
          <StatusIcon size={10} />
          {statusBadge.label}
        </div>
        <div style={{
          ...styles.semaforoBadge,
          background: semaforo.bg,
          color: semaforo.color,
        }}>
          {semaforo.label}
        </div>
      </div>

      {/* Header */}
      <div style={styles.creditHeader}>
        <div>
          <div style={styles.creditAmount}>
            ${data.monto?.toLocaleString()}
          </div>
          <div style={styles.creditDate}>
            {data.fecha_inicio ? String(data.fecha_inicio).substring(0, 10) : 'Sin fecha'}
          </div>
          <div style={styles.empresaBadge}>
            📍 {empresaNombre}
          </div>
        </div>
        <div style={styles.creditScore}>
          <div style={{...styles.creditScoreValue, color: scoreColors.text}}>
            {data.score_individual}
          </div>
          <div style={styles.creditScoreLabel}>Puntos</div>
        </div>
      </div>

      {/* Indicadores */}
      <div style={styles.indicatorsGrid}>
        <Indicator 
          label="Días Retraso"
          value={`${data.dias_retraso_final}d`}
          isBad={data.dias_retraso_final > 0}
          onInfo={() => showTooltip('Días de Retraso', 'Días extra que tomó pagar después de la fecha acordada. 0 = Pagó a tiempo o antes.')}
        />
        <Indicator 
          label="Puntualidad"
          value={`${data.frecuencia_pagos}%`}
          isBad={data.frecuencia_pagos < 70}
          onInfo={() => showTooltip('Puntualidad Diaria', 'Porcentaje de días que estuvo al día o pagó. 100% = Siempre puntual.')}
        />
        <Indicator 
          label="Atraso Prom."
          value={`${data.promedio_atraso}c`}
          isBad={data.promedio_atraso > 1}
          onInfo={() => showTooltip('Atraso Promedio', 'Cuotas promedio que debió durante la vida del crédito. 0 = Nunca debió cuotas.')}
        />
        <Indicator 
          label="Estrés Cierre"
          value={data.puntaje_atraso_cierre}
          isBad={data.puntaje_atraso_cierre > 5}
          onInfo={() => showTooltip('Estrés al Cierre', 'Suma de cuotas pendientes + días vencidos al momento del cierre. Mide la "tensión" final.')}
        />
      </div>
    </div>
  )
}

function Indicator({ label, value, isBad, onInfo }) {
  return (
    <div style={styles.indicator}>
      <div style={styles.indicatorLabel}>
        {label}
        <button 
          style={styles.infoBtn}
          onClick={onInfo}
        >
          <AlertCircle size={12} color="rgba(255,255,255,0.5)" />
        </button>
      </div>
      <div style={{
        ...styles.indicatorValue,
        color: isBad ? '#ef4444' : '#22c55e'
      }}>
        {value}
      </div>
    </div>
  )
}
