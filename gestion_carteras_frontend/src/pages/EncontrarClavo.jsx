import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import './EncontrarClavo.css'; // Crearemos este CSS o usaremos estilos inline/globales

const EncontrarClavo = () => {
  const navigate = useNavigate();
  const [identificacion, setIdentificacion] = useState('');
  const [cliente, setCliente] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searched, setSearched] = useState(false);

  const handleBuscar = async (e) => {
    e.preventDefault();
    if (!identificacion) return;

    setLoading(true);
    setError(null);
    setCliente(null);
    setSearched(false);

    try {
      const data = await apiClient.get(`/clientes/${identificacion}/rastreo`);
      setCliente(data);
    } catch (err) {
      if (err.response && err.response.status === 404) {
        setError('Cliente no encontrado en la base de datos.');
      } else {
        setError('Error al buscar el cliente. Intente nuevamente.');
        console.error(err);
      }
    } finally {
      setLoading(false);
      setSearched(true);
    }
  };

  const formatearFecha = (fecha) => {
    if (!fecha) return 'Sin registros';
    const [year, month, day] = fecha.split('-');
    return `${day}/${month}/${year}`;
  };

  return (
    <div className="encontrar-clavo-container">
      <div className="header-simple">
        <button className="back-btn" onClick={() => navigate('/')}>
          ← Volver
        </button>
        <h1>Encontrar Clavo</h1>
      </div>

      <div className="content-wrapper">
        <form onSubmit={handleBuscar} className="search-form">
          <div className="input-group">
            <label htmlFor="identificacion">Identificación</label>
            <input
              type="text"
              id="identificacion"
              value={identificacion}
              onChange={(e) => setIdentificacion(e.target.value)}
              placeholder="Ingrese cédula o NIT"
              inputMode="numeric"
              autoComplete="off"
            />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Buscando...' : 'Buscar'}
          </button>
        </form>

        <div className="info-box">
          <p>
            <strong>¿Para qué sirve esto?</strong><br/>
            Esta herramienta permite rastrear clientes que se han mudado o registrado con otra ruta en otra oficina. 
            Al ingresar la identificación, obtendrá sus datos actualizados (dirección, teléfono) 
            y la fecha de su última actividad registrada. "Para ser exacto en la direccion y ayudar a sus colegas poner la direccion completa incluyendo la ciudad en todos sus prestamos".
          </p>
        </div>

        {searched && !loading && !cliente && !error && (
            <div className="no-results">No se encontraron resultados.</div>
        )}

        {error && <div className="error-msg">{error}</div>}

        {cliente && (
          <div className="resultado-card">
            <h3>{cliente.nombre} {cliente.apellido}</h3>
            
            <div className="dato-fila">
              <span className="label">Identificación:</span>
              <span className="valor">{cliente.identificacion}</span>
            </div>

            <div className="dato-fila">
              <span className="label">Teléfono:</span>
              <span className="valor phone-link">
                {cliente.telefono ? (
                  <a href={`tel:${cliente.telefono}`}>{cliente.telefono}</a>
                ) : (
                  'No registrado'
                )}
              </span>
            </div>

            <div className="dato-fila">
              <span className="label">Dirección:</span>
              <span className="valor">{cliente.direccion || 'No registrada'}</span>
            </div>

            <div className="dato-fila destacado">
              <span className="label">Última Tarjeta:</span>
              <span className="valor">{formatearFecha(cliente.fecha_ultima_tarjeta)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EncontrarClavo;

