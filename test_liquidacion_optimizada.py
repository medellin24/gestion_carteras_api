#!/usr/bin/env python3
"""
Script de prueba para verificar la optimización del Frame de Liquidación
- Sin actualizaciones automáticas
- Solo actualización manual con botón "Generar Liquidación"
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Función principal de prueba"""
    try:
        # Importar el frame de liquidación
        from frames.frame_liquidacion import FrameLiquidacion
        
        # Crear ventana principal
        root = tk.Tk()
        root.title("Prueba - Frame Liquidación Optimizado")
        root.geometry("1200x800")
        
        # Crear notebook para simular la aplicación principal
        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Crear frame de liquidación
        frame_liquidacion = FrameLiquidacion(notebook)
        notebook.add(frame_liquidacion, text="💰 Liquidación")
        
        # Mensaje de instrucciones
        instrucciones = tk.Label(root, 
                                text="🎯 PRUEBA DE OPTIMIZACIÓN: Cambie empleado/fecha y observe que NO se actualiza automáticamente.\n"
                                     "Solo se actualiza al presionar 'Generar Liquidación'",
                                bg='#E0F2FE', fg='#0369A1', font=('Arial', 10, 'bold'),
                                wraplength=800, justify='center')
        instrucciones.pack(side='bottom', fill='x', pady=5)
        
        print("🚀 Aplicación de prueba iniciada")
        print("📋 Instrucciones:")
        print("   1. Seleccione un empleado")
        print("   2. Cambie la fecha")
        print("   3. Observe que los cálculos NO se actualizan automáticamente")
        print("   4. Presione 'Generar Liquidación' para actualizar")
        print("   5. Observe la ventana de carga 'Generando Liquidación'")
        
        # Iniciar aplicación
        root.mainloop()
        
    except Exception as e:
        print(f"❌ Error al iniciar la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 