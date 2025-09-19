#!/usr/bin/env python3
"""
Script de prueba rápido para verificar que el error de barra_estado esté corregido
"""

import tkinter as tk
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ventana_principal():
    """Prueba que la VentanaPrincipal se inicialice sin errores"""
    try:
        print("🧪 Iniciando test de VentanaPrincipal...")
        
        # Crear ventana root
        root = tk.Tk()
        root.withdraw()  # Ocultar ventana para test rápido
        
        # Importar y crear VentanaPrincipal
        from frames.ventana_principal import VentanaPrincipal
        app = VentanaPrincipal(root)
        
        print("✅ VentanaPrincipal creada exitosamente")
        
        # Verificar que la barra de estado existe
        if hasattr(app, 'barra_estado'):
            print("✅ barra_estado existe correctamente")
        else:
            print("❌ barra_estado NO existe")
            return False
        
        # Verificar que el cache está inicializado
        if hasattr(app, 'frames_cache'):
            print(f"✅ frames_cache inicializado: {len(app.frames_cache)} frames")
        else:
            print("❌ frames_cache NO existe")
            return False
        
        # Probar cambio de frame (sin mostrar ventana)
        print("🔄 Probando cambio de frames...")
        
        # El frame inicial (Entrega) ya debería estar cargado
        if 'Entrega' in app.frames_cache:
            print("✅ Frame Entrega cargado automáticamente")
        
        # Probar cargar otros frames
        try:
            app.mostrar_liquidacion()
            print("✅ Frame Liquidación cargado")
        except Exception as e:
            print(f"❌ Error al cargar Liquidación: {e}")
            return False
        
        try:
            app.mostrar_empleado()
            print("✅ Frame Empleado cargado")
        except Exception as e:
            print(f"❌ Error al cargar Empleado: {e}")
            return False
        
        try:
            app.mostrar_finanzas()
            print("✅ Frame Finanzas cargado")
        except Exception as e:
            print(f"❌ Error al cargar Finanzas: {e}")
            return False
        
        # Verificar cache final
        print(f"📊 Frames en cache final: {len(app.frames_cache)}")
        for nombre in app.frames_cache.keys():
            print(f"   - {nombre}")
        
        # Cerrar ventana
        root.destroy()
        
        print("🎉 ¡Todos los tests pasaron exitosamente!")
        return True
        
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal"""
    print("🚀 Test de corrección de barra_estado")
    print("=" * 50)
    
    if test_ventana_principal():
        print("=" * 50)
        print("✅ RESULTADO: Error de barra_estado CORREGIDO")
        print("✅ La aplicación debería funcionar correctamente ahora")
    else:
        print("=" * 50)
        print("❌ RESULTADO: Aún hay errores")
        print("❌ Revisar la implementación")

if __name__ == "__main__":
    main() 