#!/usr/bin/env python3
"""
Script de prueba para verificar la optimización de navegación entre frames
- Sin recrear frames en cada cambio
- Cache compartido de empleados
- Navegación instantánea
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
import time
import logging

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configurar logging para monitorear consultas
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class TestNavigationWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 Test - Navegación Optimizada entre Frames")
        self.root.geometry("1200x800")
        
        # Variables para medir tiempos
        self.tiempo_inicio = 0
        self.contador_cambios = 0
        
        self.setup_ui()
    
    def setup_ui(self):
        """Configura la interfaz de prueba"""
        
        # Panel de instrucciones
        instrucciones = tk.Label(self.root, 
                                text="🎯 PRUEBA DE OPTIMIZACIÓN DE NAVEGACIÓN\n\n"
                                     "✅ Primera vez: Puede tardar (carga inicial)\n"
                                     "⚡ Siguientes veces: Debe ser INSTANTÁNEO\n\n"
                                     "Navegue entre frames y observe los tiempos:",
                                bg='#E3F2FD', fg='#1565C0', font=('Arial', 11, 'bold'),
                                wraplength=800, justify='center', pady=10)
        instrucciones.pack(fill='x', pady=5)
        
        # Panel de métricas
        self.frame_metricas = tk.Frame(self.root, bg='#F5F5F5', height=60)
        self.frame_metricas.pack(fill='x', pady=5)
        self.frame_metricas.pack_propagate(False)
        
        # Métricas de rendimiento
        self.lbl_tiempo = tk.Label(self.frame_metricas, 
                                  text="⏱️ Tiempo último cambio: --", 
                                  font=('Arial', 10, 'bold'), bg='#F5F5F5')
        self.lbl_tiempo.pack(side='left', padx=20, pady=15)
        
        self.lbl_contador = tk.Label(self.frame_metricas, 
                                    text="🔄 Cambios realizados: 0", 
                                    font=('Arial', 10, 'bold'), bg='#F5F5F5')
        self.lbl_contador.pack(side='left', padx=20, pady=15)
        
        self.lbl_cache = tk.Label(self.frame_metricas, 
                                 text="💾 Frames en cache: 0", 
                                 font=('Arial', 10, 'bold'), bg='#F5F5F5')
        self.lbl_cache.pack(side='left', padx=20, pady=15)
        
        # Separador
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', pady=5)
        
        # Importar y crear la ventana principal optimizada
        try:
            from frames.ventana_principal import VentanaPrincipal
            
            # Crear contenedor para la aplicación
            app_container = tk.Frame(self.root)
            app_container.pack(fill='both', expand=True)
            
            # Crear la ventana principal dentro del contenedor
            self.app = VentanaPrincipal(app_container)
            
            # Interceptar los métodos de cambio de frame para medir tiempos
            self.interceptar_metodos_navegacion()
            
        except Exception as e:
            error_label = tk.Label(self.root, 
                                  text=f"❌ Error al cargar aplicación: {e}",
                                  fg='red', font=('Arial', 12, 'bold'))
            error_label.pack(pady=50)
    
    def interceptar_metodos_navegacion(self):
        """Intercepta los métodos de navegación para medir tiempos"""
        
        # Guardar métodos originales
        original_entrega = self.app.mostrar_entrega
        original_liquidacion = self.app.mostrar_liquidacion
        original_empleado = self.app.mostrar_empleado
        original_finanzas = self.app.mostrar_finanzas
        
        # Crear wrappers que miden tiempo
        def wrapper_entrega():
            self.medir_tiempo("Entrega", original_entrega)
        
        def wrapper_liquidacion():
            self.medir_tiempo("Liquidación", original_liquidacion)
        
        def wrapper_empleado():
            self.medir_tiempo("Empleado", original_empleado)
        
        def wrapper_finanzas():
            self.medir_tiempo("Finanzas", original_finanzas)
        
        # Reemplazar métodos
        self.app.mostrar_entrega = wrapper_entrega
        self.app.mostrar_liquidacion = wrapper_liquidacion
        self.app.mostrar_empleado = wrapper_empleado
        self.app.mostrar_finanzas = wrapper_finanzas
    
    def medir_tiempo(self, nombre_frame, metodo_original):
        """Mide el tiempo que tarda en cambiar de frame"""
        tiempo_inicio = time.time()
        
        # Ejecutar método original
        metodo_original()
        
        tiempo_fin = time.time()
        tiempo_transcurrido = (tiempo_fin - tiempo_inicio) * 1000  # En milisegundos
        
        # Actualizar contador
        self.contador_cambios += 1
        
        # Actualizar métricas en la interfaz
        self.actualizar_metricas(nombre_frame, tiempo_transcurrido)
        
        # Log del resultado
        if tiempo_transcurrido < 100:
            nivel = "✅ EXCELENTE"
            color = "#4CAF50"
        elif tiempo_transcurrido < 500:
            nivel = "🟡 BUENO"
            color = "#FF9800"
        else:
            nivel = "❌ LENTO"
            color = "#F44336"
        
        print(f"{nivel} - {nombre_frame}: {tiempo_transcurrido:.1f}ms")
    
    def actualizar_metricas(self, nombre_frame, tiempo_ms):
        """Actualiza las métricas mostradas en la interfaz"""
        
        # Actualizar tiempo
        if tiempo_ms < 100:
            color_tiempo = "#4CAF50"  # Verde
            estado = "⚡ INSTANTÁNEO"
        elif tiempo_ms < 500:
            color_tiempo = "#FF9800"  # Naranja
            estado = "🟡 ACEPTABLE"
        else:
            color_tiempo = "#F44336"  # Rojo
            estado = "❌ LENTO"
        
        self.lbl_tiempo.config(
            text=f"⏱️ {nombre_frame}: {tiempo_ms:.1f}ms - {estado}",
            fg=color_tiempo
        )
        
        # Actualizar contador
        self.lbl_contador.config(text=f"🔄 Cambios realizados: {self.contador_cambios}")
        
        # Actualizar cache
        frames_en_cache = len(self.app.frames_cache) if hasattr(self.app, 'frames_cache') else 0
        self.lbl_cache.config(text=f"💾 Frames en cache: {frames_en_cache}")

def main():
    """Función principal de prueba"""
    try:
        root = tk.Tk()
        test_app = TestNavigationWindow(root)
        
        print("🚀 Test de navegación iniciado")
        print("📋 Instrucciones:")
        print("   1. Navegue entre los frames: Entrega, Liquidación, Empleado, Finanzas")
        print("   2. La primera vez puede tardar (carga inicial)")
        print("   3. Las siguientes veces deben ser instantáneas (<100ms)")
        print("   4. Observe las métricas en la parte superior")
        print("   5. Los tiempos se muestran en la consola")
        print()
        
        root.mainloop()
        
    except Exception as e:
        print(f"❌ Error al iniciar la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 