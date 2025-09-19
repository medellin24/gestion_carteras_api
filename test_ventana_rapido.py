#!/usr/bin/env python3
"""
Script de prueba rápida para verificar que la ventana de eliminación se abre sin errores.
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ventana_rapida():
    """Prueba rápida de la ventana de eliminación."""
    print("🧪 Iniciando prueba rápida de la ventana de eliminación...")
    
    # Crear ventana principal
    root = tk.Tk()
    root.title("Prueba Rápida - Ventana de Eliminación")
    root.geometry("400x300")
    
    # Datos de prueba
    empleado_prueba = {
        'identificacion': '1045112243',
        'nombre_completo': 'Jorge Alejandro San Jose',
        'telefono': '3112027405',
        'direccion': 'Calle 17 # 24-138'
    }
    
    def callback_actualizar():
        print("✅ Callback de actualización ejecutado")
    
    def mock_api_client():
        """Mock del API client para pruebas"""
        class MockAPIClient:
            def delete_empleado(self, identificacion):
                # Simular que tiene tarjetas asociadas
                raise Exception("Empleado tiene tarjetas asociadas")
            
            def list_empleados(self):
                return [
                    {'identificacion': '1234567890', 'nombre_completo': 'Empleado Destino 1'},
                    {'identificacion': '0987654321', 'nombre_completo': 'Empleado Destino 2'},
                ]
            
            def transferir_tarjetas_empleado(self, origen, destino):
                print(f"✅ Transferencia simulada: {origen} -> {destino}")
                return {"ok": True}
            
            def eliminar_empleado_forzado(self, identificacion):
                print(f"✅ Eliminación forzada simulada: {identificacion}")
                return {"ok": True}
        
        return MockAPIClient()
    
    try:
        # Importar la clase de la ventana
        from frames.frame_empleado import VentanaEliminarEmpleado
        
        # Crear botón para abrir la ventana
        def abrir_ventana():
            try:
                VentanaEliminarEmpleado(
                    parent=root,
                    callback_actualizar=callback_actualizar,
                    api_client=mock_api_client(),
                    empleado_data=empleado_prueba
                )
                print("✅ Ventana abierta exitosamente")
            except Exception as e:
                print(f"❌ Error al abrir ventana: {e}")
                import traceback
                traceback.print_exc()
        
        # Botón para abrir la ventana de prueba
        btn_abrir = tk.Button(
            root, 
            text="🧪 Abrir Ventana de Eliminación",
            font=('Arial', 12, 'bold'),
            bg='blue', fg='white',
            command=abrir_ventana
        )
        btn_abrir.pack(pady=20)
        
        # Información de prueba
        info_frame = ttk.LabelFrame(root, text="Información de Prueba", padding="10")
        info_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(info_frame, text=f"👤 Empleado: {empleado_prueba['nombre_completo']}").pack(anchor='w')
        ttk.Label(info_frame, text=f"🆔 ID: {empleado_prueba['identificacion']}").pack(anchor='w')
        ttk.Label(info_frame, text="📋 Estado: Simula tener tarjetas asociadas").pack(anchor='w')
        
        # Botón de salir
        btn_salir = tk.Button(
            root, 
            text="❌ Salir",
            font=('Arial', 10),
            command=root.quit
        )
        btn_salir.pack(pady=10)
        
        print("✅ Ventana de prueba creada exitosamente")
        print("📋 Instrucciones:")
        print("   - Haz clic en 'Abrir Ventana de Eliminación'")
        print("   - Verifica que se abra sin errores")
        
        # Ejecutar la aplicación
        root.mainloop()
        
    except ImportError as e:
        print(f"❌ Error al importar la ventana: {e}")
        print("💡 Asegúrate de que el archivo frame_empleado.py esté en la carpeta frames/")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ventana_rapida()
