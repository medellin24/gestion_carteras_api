#!/usr/bin/env python3
"""
Script para procesar íconos existentes en assets/icons/
Toma todos los archivos PNG y los redimensiona, centra y crea fondo transparente
"""

import os
import glob
from PIL import Image

def procesar_icono(img_path, ancho, alto):
    """Procesa un ícono individual usando el código proporcionado"""
    try:
        # Abrir imagen original
        img = Image.open(img_path)
        
        # Calcular proporciones manteniendo aspecto
        img.thumbnail((ancho, alto), Image.LANCZOS)
        
        # Crear fondo transparente
        new_img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
        
        # Centrar
        x = (ancho - img.width) // 2
        y = (alto - img.height) // 2
        new_img.paste(img, (x, y), img if img.mode == 'RGBA' else None)
        
        return new_img
        
    except Exception as e:
        print(f"❌ Error procesando {img_path}: {e}")
        return None

def procesar_todos_los_iconos():
    """Procesa todos los PNG en assets/icons/"""
    
    icons_dir = "assets/icons"
    
    if not os.path.exists(icons_dir):
        print(f"❌ No se encontró la carpeta: {icons_dir}")
        return
    
    # Buscar todos los archivos PNG
    archivos_png = glob.glob(os.path.join(icons_dir, "*.png"))
    
    if not archivos_png:
        print(f"⚠️  No se encontraron archivos PNG en {icons_dir}")
        return
    
    print(f"🎨 Procesando {len(archivos_png)} archivos PNG...")
    print("=" * 50)
    
    # Tamaños específicos para diferentes tipos de íconos
    tamanos_iconos = {
        # Ícono grande del perfil
        'profile_right': (176, 196),
        
        # Íconos de botones (24x24)
        'add': (24, 24),
        'edit': (24, 24), 
        'delete': (24, 24),
        'collector': (24, 24),
        'search': (24, 24),
        'date': (24, 24),
        'money': (24, 24),
        'user': (24, 24),
        
        # Íconos de etiquetas (16x16)
        'id': (16, 16),
        'phone': (16, 16),
        'address': (16, 16),
    }
    
    for archivo in archivos_png:
        nombre_archivo = os.path.basename(archivo)
        nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
        
        # Determinar el tamaño basado en el nombre del archivo
        if nombre_sin_ext in tamanos_iconos:
            ancho, alto = tamanos_iconos[nombre_sin_ext]
            print(f"🔄 Procesando {nombre_archivo} -> {ancho}x{alto}")
        else:
            # Tamaño por defecto para archivos no reconocidos
            ancho, alto = 24, 24
            print(f"🔄 Procesando {nombre_archivo} -> {ancho}x{alto} (tamaño por defecto)")
        
        # Procesar el ícono
        img_procesada = procesar_icono(archivo, ancho, alto)
        
        if img_procesada:
            # Guardar con el mismo nombre (sobrescribe el original)
            img_procesada.save(archivo, "PNG")
            print(f"✅ {nombre_archivo} procesado y guardado")
        else:
            print(f"❌ Error procesando {nombre_archivo}")
        
        print("-" * 30)
    
    print("\n🎉 ¡Todos los íconos han sido procesados!")

def main():
    print("🎨 PROCESADOR DE ÍCONOS EXISTENTES")
    print("=" * 40)
    print("Este script procesará todos los PNG en assets/icons/")
    print("Los archivos serán redimensionados, centrados y con fondo transparente")
    print()
    
    confirmar = input("¿Continuar? (s/n): ").lower().strip()
    if confirmar == 's':
        procesar_todos_los_iconos()
    else:
        print("❌ Operación cancelada")

if __name__ == "__main__":
    main()
