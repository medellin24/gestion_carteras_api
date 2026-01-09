import tkinter as tk
from tkinter import ttk
from tkcalendar import Calendar
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class DateSelector(ttk.Frame):
    def __init__(self, parent, date_pattern='%Y-%m-%d', width=12, textvariable=None, **kwargs):
        super().__init__(parent)
        self.date_pattern = date_pattern
        self.python_pattern = self._normalize_pattern(date_pattern)
        
        if textvariable:
            self.fecha_var = textvariable
        else:
            self.fecha_var = tk.StringVar()
        
        self.entry = ttk.Entry(self, textvariable=self.fecha_var, width=width)
        self.entry.pack(side='left', fill='y', expand=True)
        
        self.btn_cal = tk.Button(self, text='📅', width=3, cursor='hand2',
                                 command=self.abrir_calendario,
                                 relief='raised', bd=1)
        self.btn_cal.pack(side='left', padx=(2, 0))
        
        self.event_name = '<<DateSelected>>'

    def _normalize_pattern(self, pattern):
        # Convert common tkcalendar patterns to strftime patterns
        return pattern.replace('yyyy', '%Y').replace('mm', '%m').replace('dd', '%d').replace('MM', '%m')

    def set_date(self, fecha):
        if isinstance(fecha, (date, datetime)):
            self.fecha_var.set(fecha.strftime(self.python_pattern))
        elif isinstance(fecha, str):
            self.fecha_var.set(fecha)

    def get_date(self):
        try:
            val = self.fecha_var.get()
            return datetime.strptime(val, self.python_pattern).date()
        except ValueError:
            return None
    
    def get(self):
        return self.fecha_var.get()

    def abrir_calendario(self):
        top = tk.Toplevel(self)
        top.title("Seleccionar Fecha")
        top.transient(self.winfo_toplevel())
        top.grab_set()
        
        # Configurar el contenido primero para saber el tamaño
        try:
            cal = Calendar(top, selectmode='day', locale='es_ES', cursor="hand2")
        except Exception as e:
            logger.warning(f"Failed to load es_ES locale for Calendar, falling back to default: {e}")
            cal = Calendar(top, selectmode='day', cursor="hand2")
        
        cal.pack(fill="both", expand=True, padx=5, pady=5)
        
        try:
            current = self.get_date()
            if current:
                cal.selection_set(current)
        except:
            pass

        def on_select(evt=None):
            sel = cal.selection_get()
            self.set_date(sel)
            self.event_generate(self.event_name)
            top.destroy()
        
        cal.bind("<<CalendarSelected>>", on_select)
        
        def ir_hoy():
            today = date.today()
            cal.selection_set(today)
            on_select()
            
        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Hoy", command=ir_hoy).pack(side='left', padx=5, expand=True)
        ttk.Button(btn_frame, text="Cerrar", command=top.destroy).pack(side='right', padx=5, expand=True)

        # Calcular posición: Alinear borde derecho del calendario con borde derecho del botón
        try:
            top.update_idletasks() # Forzar cálculo de dimensiones
            
            btn_x_root = self.btn_cal.winfo_rootx()
            btn_y_root = self.btn_cal.winfo_rooty()
            btn_width = self.btn_cal.winfo_width()
            btn_height = self.btn_cal.winfo_height()
            
            cal_width = top.winfo_reqwidth()
            cal_height = top.winfo_reqheight()
            
            # Coordenada X: Borde derecho botón - Ancho calendario
            # (btn_x_root + btn_width) es el borde derecho absoluto del botón
            x = (btn_x_root + btn_width) - cal_width
            
            # Coordenada Y: Debajo del botón + un pequeño margen
            y = btn_y_root + btn_height + 2
            
            top.geometry(f"+{x}+{y}")
        except:
            # Fallback a posición simple si falla el cálculo
            try:
                x = self.btn_cal.winfo_rootx()
                y = self.btn_cal.winfo_rooty() + self.btn_cal.winfo_height()
                top.geometry(f"+{x}+{y}")
            except:
                pass
        
        # Cerrar si se hace clic fuera (opcional, pero útil para comportamiento popup)
        def close_on_click_outside(event):
            # Si el clic no es en el widget 'top' ni en sus descendientes
            try:
                if event.widget != top and str(event.widget).startswith(str(top)) == False:
                     top.destroy()
            except:
                pass
        
        # Binding global para detectar clics fuera (con cuidado)
        # top.bind("<FocusOut>", lambda e: top.destroy()) # A veces conflictivo con los botones internos

