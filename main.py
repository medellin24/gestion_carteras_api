import tkinter as tk
import sys
import os
import logging

# Se elimina el fix de rutas, ya no es necesario con la nueva estructura plana.
# Ahora las importaciones son directas.

from frames.ventana_principal import VentanaPrincipal
from frames.ventana_login import VentanaLogin

# Configurar logging para la aplicación de escritorio
logging.basicConfig(
    level=logging.INFO, # Cambiado de DEBUG a INFO para producción
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app_escritorio.log', # Guardar logs en un archivo
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
        # Login OK, mostrar principal
        root.deiconify()
        app = VentanaPrincipal(root)
        root.mainloop()
        logger.info("Aplicación de escritorio cerrada.")
    except Exception as e:
        logger.critical(f"Error fatal en la aplicación: {e}", exc_info=True)
        # Opcional: mostrar un messagebox al usuario antes de cerrar
        # tk.messagebox.showerror("Error Crítico", "La aplicación encontró un error fatal y debe cerrarse.")
        raise

if __name__ == "__main__":
    main()
    