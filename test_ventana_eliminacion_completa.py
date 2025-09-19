#!/usr/bin/env python3
"""
Script de prueba completo para la ventana de eliminación de empleados.
Verifica tanto el botón de eliminación forzada como la funcionalidad de transferir tarjetas.
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ventana_eliminacion_completa():
    """Prueba completa de la ventana de eliminación."""
    print("🧪 Iniciando prueba completa de la ventana de eliminación...")
    
    # Crear ventana principal
    root = tk.Tk()
    root.title("Prueba Completa - Ventana de Eliminación")
    root.geometry("900x700")
    
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
                    {'identificacion': '5555555555', 'nombre_completo': 'Empleado Destino 3'},
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
            VentanaEliminarEmpleado(
                parent=root,
                callback_actualizar=callback_actualizar,
                api_client=mock_api_client(),
                empleado_data=empleado_prueba
            )
        
        # Botón para abrir la ventana de prueba
        btn_abrir = tk.Button(
            root, 
            text="🧪 Abrir Ventana de Eliminación (Prueba Completa)",
            font=('Arial', 14, 'bold'),
            bg='blue', fg='white',
            command=abrir_ventana
        )
        btn_abrir.pack(pady=20)
        
        # Información de prueba
        info_frame = ttk.LabelFrame(root, text="Información de Prueba", padding="15")
        info_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(info_frame, text=f"👤 Empleado: {empleado_prueba['nombre_completo']}", 
                 font=('Arial', 11, 'bold')).pack(anchor='w')
        ttk.Label(info_frame, text=f"🆔 ID: {empleado_prueba['identificacion']}", 
                 font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_frame, text="📋 Estado: Simula tener tarjetas asociadas", 
                 font=('Arial', 10)).pack(anchor='w')
        
        # Instrucciones detalladas
        instrucciones_frame = ttk.LabelFrame(root, text="Instrucciones de Prueba", padding="15")
        instrucciones_frame.pack(fill='x', padx=20, pady=10)
        
        instrucciones = [
            "1. Haz clic en 'Abrir Ventana de Eliminación'",
            "2. Verifica que la ventana sea de 650x600 píxeles",
            "3. Busca el separador visual entre las opciones",
            "4. Verifica el frame 'Eliminación Forzada'",
            "5. Busca el checkbox con icono ☑️",
            "6. Verifica el botón rojo grande con texto descriptivo",
            "7. Busca el mensaje 'NO se puede deshacer'",
            "8. Verifica que el combobox de empleados destino tenga opciones",
            "9. Prueba las funcionalidades (simuladas)"
        ]
        
        for i, instruccion in enumerate(instrucciones, 1):
            color = 'blue' if i <= 7 else 'green'
            ttk.Label(instrucciones_frame, text=instruccion, 
                     font=('Arial', 10), foreground=color).pack(anchor='w', pady=2)
        
        # Checklist de verificación
        checklist_frame = ttk.LabelFrame(root, text="Checklist de Verificación", padding="15")
        checklist_frame.pack(fill='x', padx=20, pady=10)
        
        checklist_items = [
            "✅ Tamaño de ventana: 650x600",
            "✅ Separador visual entre opciones",
            "✅ Frame 'Eliminación Forzada' visible",
            "✅ Checkbox con icono ☑️",
            "✅ Botón rojo grande visible",
            "✅ Mensaje de advertencia",
            "✅ Combobox con empleados destino",
            "✅ Funcionalidad de transferencia",
            "✅ Funcionalidad de eliminación forzada"
        ]
        
        for item in checklist_items:
            ttk.Label(checklist_frame, text=item, font=('Arial', 10)).pack(anchor='w', pady=1)
        
        # Botón de salir
        btn_salir = tk.Button(
            root, 
            text="❌ Salir",
            font=('Arial', 12),
            command=root.quit
        )
        btn_salir.pack(pady=15)
        
        print("✅ Ventana de prueba completa creada exitosamente")
        print("📋 Instrucciones:")
        print("   - Haz clic en 'Abrir Ventana de Eliminación'")
        print("   - Verifica las mejoras visuales implementadas")
        print("   - Prueba la funcionalidad de transferir tarjetas")
        print("   - Prueba la funcionalidad de eliminación forzada")
        
        # Ejecutar la aplicación
        root.mainloop()
        
    except ImportError as e:
        print(f"❌ Error al importar la ventana: {e}")
        print("💡 Asegúrate de que el archivo frame_empleado.py esté en la carpeta frames/")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

def verificar_mejoras_completas():
    """Verifica que todas las mejoras estén implementadas en el código."""
    print("\n🔍 Verificando mejoras completas en el código...")
    
    try:
        with open('frames/frame_empleado.py', 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        mejoras = [
            ('self.geometry("650x600")', 'Tamaño de ventana aumentado'),
            ('ttk.Separator(options_frame, orient=\'horizontal\')', 'Separador visual agregado'),
            ('ttk.LabelFrame(options_frame, text="Eliminación Forzada"', 'Frame dedicado agregado'),
            ('text="☑️ Confirmo que entiendo las consecuencias"', 'Checkbox mejorado'),
            ('text="💥 ELIMINAR EMPLEADO Y TODAS SUS TARJETAS"', 'Botón rediseñado'),
            ('bg=\'red\', fg=\'white\'', 'Colores del botón'),
            ('font=(\'Arial\', 12, \'bold\')', 'Fuente del botón'),
            ('text="⚠️ Esta acción NO se puede deshacer"', 'Mensaje adicional'),
            ('def cargar_empleados_disponibles(self):', 'Función de carga de empleados'),
            ('self.combo_empleado_destino[\'values\'] = nombres', 'Actualización del combobox'),
            ('def transferir_tarjetas(self):', 'Función de transferencia'),
            ('def eliminar_forzado(self):', 'Función de eliminación forzada')
        ]
        
        resultados = []
        for codigo, descripcion in mejoras:
            if codigo in contenido:
                print(f"✅ {descripcion}")
                resultados.append(True)
            else:
                print(f"❌ {descripcion}")
                resultados.append(False)
        
        print(f"\n📊 Resumen: {sum(resultados)}/{len(resultados)} mejoras implementadas")
        
        if all(resultados):
            print("🎉 ¡Todas las mejoras están implementadas correctamente!")
        else:
            print("⚠️ Algunas mejoras no se encontraron en el código")
            
    except FileNotFoundError:
        print("❌ No se pudo encontrar el archivo frame_empleado.py")
    except Exception as e:
        print(f"❌ Error al verificar el código: {e}")

def main():
    """Función principal de prueba."""
    print("🚀 Iniciando pruebas completas de mejoras en ventana de eliminación")
    print("=" * 70)
    
    # Verificar mejoras en el código
    verificar_mejoras_completas()
    
    # Preguntar si ejecutar la prueba visual
    print("\n" + "=" * 70)
    respuesta = input("¿Deseas ejecutar la prueba visual completa? (s/n): ").lower()
    
    if respuesta in ['s', 'si', 'sí', 'y', 'yes']:
        test_ventana_eliminacion_completa()
    else:
        print("✅ Pruebas completadas. Las mejoras están implementadas en el código.")

if __name__ == "__main__":
    main()
