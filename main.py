import tkinter as tk
import sys
import os
import logging

# Se elimina el fix de rutas, ya no es necesario con la nueva estructura plana.
# Ahora las importaciones son directas.

from frames.ventana_principal import VentanaPrincipal
from frames.ventana_login import VentanaLogin

# Configurar logging para la aplicación de escritorio
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
if getattr(sys, 'frozen', False):
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT
    )
else:
    logging.basicConfig(
        level=logging.INFO,  # Cambiado de DEBUG a INFO para producción
        format=LOG_FORMAT,
        filename='app_escritorio.log',  # Guardar logs en un archivo solo en desarrollo
        filemode='a'
    )
logger = logging.getLogger(__name__)

def main():
    try:
        # Crear y ejecutar la aplicación
        logger.info("Iniciando la aplicación de escritorio...")
        root = tk.Tk()
        root.withdraw()  # ocultar ventana hasta logueo
        dlg = VentanaLogin(master=root)
        dlg.wait_window()
        if not getattr(dlg, 'result', None):
            logger.info("Login cancelado o fallido. Cerrando aplicación.")
            return
        # Login OK, obtener datos del usuario
        login_data = dlg.result
        user_email = login_data[2] if login_data and len(login_data) > 2 else 'usuario@ejemplo.com'
        # Mostrar principal
        root.deiconify()
        # Posicionar la ventana a 15 píxeles de la parte superior
        try:
            root.update_idletasks()
            w = root.winfo_width() or 1200
            h = root.winfo_height() or 700
            sw = root.winfo_screenwidth()
            # Centrar horizontalmente y posicionar a 15px del borde superior
            x = max((sw // 2) - (w // 2), 0)
            y = 15
            root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass
        app = VentanaPrincipal(root, user_email)
        root.mainloop()
        logger.info("Aplicación de escritorio cerrada.")
    except Exception as e:
        logger.critical(f"Error fatal en la aplicación: {e}", exc_info=True)
        # Opcional: mostrar un messagebox al usuario antes de cerrar
        # tk.messagebox.showerror("Error Crítico", "La aplicación encontró un error fatal y debe cerrarse.")
        raise

if __name__ == "__main__":
    main()
    