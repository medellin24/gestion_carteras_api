#!/usr/bin/env python3
"""
Script para procesar íconos existentes en assets/icons/
Toma todos los archivos PNG y los redimensiona.
MEJORAS:
- Soporte para imagen de login grande.
- Modo 'fill' para íconos de app (home) para evitar bordes vacíos.
"""

import os
import glob
from PIL import Image, ImageOps

def procesar_icono(img_path, ancho, alto, modo='fit'):
    """
    Procesa un ícono.
    modo 'fit': Mantiene la imagen completa y rellena con transparencia (default).
    modo 'fill': Recorta la imagen para llenar todo el espacio (ideal para íconos de app).
    """
    try:
        # Abrir imagen original
        img = Image.open(img_path)
        
        # Convertir a RGBA si no lo es
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        if modo == 'fill':
            # Llenar el espacio (recortando si es necesario)
            new_img = ImageOps.fit(img, (ancho, alto), method=Image.LANCZOS, centering=(0.5, 0.5))
        else:
            # Comportamiento original: ajustar dentro (thumbnail) y centrar
            img.thumbnail((ancho, alto), Image.LANCZOS)
            new_img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
            # Centrar
            x = (ancho - img.width) // 2
            y = (alto - img.height) // 2
            new_img.paste(img, (x, y), img)
        
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
    
    archivos_png = glob.glob(os.path.join(icons_dir, "*.png"))
    
    if not archivos_png:
        print(f"⚠️  No se encontraron archivos PNG en {icons_dir}")
        return
    
    print(f"🎨 Procesando {len(archivos_png)} archivos PNG...")
    print("=" * 50)
    
    # Configuración: (ancho, alto, modo)
    # modo 'fill' evita bordes transparentes/blancos en íconos de app
    config_iconos = {
        # Imágenes grandes
        'login_image': (460, 360, 'fill'),  # AHORA TIENE TAMAÑO CORRECTO
        'profile_right': (176, 196, 'fit'),
        
        # Íconos de App (PWA / Launcher) - Usamos 'fill' para quitar bordes
        'home': (194, 194, 'fill'),
        'app_store': (512, 512, 'fill'),
        'google_play': (512, 512, 'fill'),

        # Íconos de UI (24x24)
        'add': (24, 24, 'fit'),
        'edit': (24, 24, 'fit'), 
        'delete': (24, 24, 'fit'),
        'collector': (24, 24, 'fit'),
        'search': (24, 24, 'fit'),
        'date': (24, 24, 'fit'),
        'money': (24, 24, 'fit'),
        'user': (24, 24, 'fit'),
        
        # Íconos pequeños (16x16)
        'id': (16, 16, 'fit'),
        'phone': (16, 16, 'fit'),
        'address': (16, 16, 'fit'),
    }
    
    for archivo in archivos_png:
        nombre_archivo = os.path.basename(archivo)
        nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
        
        # Determinar configuración
        if nombre_sin_ext in config_iconos:
            ancho, alto, modo = config_iconos[nombre_sin_ext]
            print(f"🔄 Procesando {nombre_archivo} -> {ancho}x{alto} (modo: {modo})")
        else:
            ancho, alto, modo = 24, 24, 'fit'
            print(f"🔄 Procesando {nombre_archivo} -> {ancho}x{alto} (default)")
        
        img_procesada = procesar_icono(archivo, ancho, alto, modo)
        
        if img_procesada:
            img_procesada.save(archivo, "PNG")
            print(f"✅ {nombre_archivo} guardado")
        else:
            print(f"❌ Error en {nombre_archivo}")
        
        print("-" * 30)
    
    print("\n🎉 ¡Proceso terminado!")

if __name__ == "__main__":
    procesar_todos_los_iconos()
