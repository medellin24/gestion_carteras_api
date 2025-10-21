#!/usr/bin/env python3
"""
Script para procesar un ícono individual
Uso: python procesar_icono_individual.py archivo.png ancho alto
"""

import sys
import os
from PIL import Image

def procesar_icono_individual(archivo_entrada, ancho, alto):
    """Procesa un ícono usando el código exacto proporcionado"""
    
    if not os.path.exists(archivo_entrada):
        print(f"❌ No se encontró: {archivo_entrada}")
        return False
    
    try:
        print(f"🔄 Procesando: {archivo_entrada}")
        print(f"📏 Tamaño objetivo: {ancho}x{alto}")
        
        # Abrir imagen original
        img = Image.open(archivo_entrada)
        print(f"📷 Imagen original: {img.size}")
        
        # Calcular proporciones
        img.thumbnail((ancho, alto), Image.LANCZOS)
        print(f"📐 Después de thumbnail: {img.size}")
        
        # Crear fondo transparente
        new_img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
        
        # Centrar
        x = (ancho - img.width) // 2
        y = (alto - img.height) // 2
        print(f"📍 Posición de centrado: ({x}, {y})")
        
        new_img.paste(img, (x, y), img if img.mode == 'RGBA' else None)
        
        # Guardar resultado
        new_img.save(archivo_entrada, "PNG")
        print(f"✅ Guardado como: {archivo_entrada}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    if len(sys.argv) != 4:
        print("🎨 PROCESADOR DE ÍCONO INDIVIDUAL")
        print("=" * 40)
        print("Uso: python procesar_icono_individual.py archivo.png ancho alto")
        print("\nEjemplos:")
        print("python procesar_icono_individual.py assets/icons/profile_right.png 176 196")
        print("python procesar_icono_individual.py assets/icons/add.png 24 24")
        return
    
    archivo = sys.argv[1]
    ancho = int(sys.argv[2])
    alto = int(sys.argv[3])
    
    print("🔄 Procesando ícono individual...")
    print("-" * 40)
    
    if procesar_icono_individual(archivo, ancho, alto):
        print("\n🎉 ¡Ícono procesado exitosamente!")
    else:
        print("\n💥 Error procesando el ícono")

if __name__ == "__main__":
    main()
