import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
from decimal import Decimal
import logging
from tkcalendar import DateEntry
from api_client.client import api_client

logger = logging.getLogger(__name__)

class VentanaEditarTarjeta:
    def __init__(self, parent, tarjeta_codigo):
        self.parent = parent
        self.tarjeta_codigo = tarjeta_codigo
        self.tarjeta_data = None
        self.cliente_data = None
        
        # Crear ventana
        self.ventana = tk.Toplevel(parent)
        self.ventana.title(f"Editar Tarjeta - {tarjeta_codigo}")
        self.ventana.geometry("720x540")
        self.ventana.minsize(680, 500)
        self.ventana.resizable(True, True)
        
        # Hacer la ventana modal
        self.ventana.transient(parent)
        self.ventana.grab_set()
        
        # Centrar la ventana
        self.centrar_ventana()
        
        # Cargar datos de la tarjeta
        self.cargar_datos()
        
        # Configurar UI
        self.setup_ui()
        
        # Llenar campos con datos actuales
        self.llenar_campos()

    def centrar_ventana(self):
        """Centra la ventana en la pantalla"""
        self.ventana.update_idletasks()
        width = self.ventana.winfo_width()
        height = self.ventana.winfo_height()
        x = (self.ventana.winfo_screenwidth() // 2) - (width // 2)
        y = (self.ventana.winfo_screenheight() // 2) - (height // 2)
        self.ventana.geometry(f'{width}x{height}+{x}+{y}')

    def cargar_datos(self):
        """Carga los datos actuales de la tarjeta y cliente"""
        try:
            # Obtener datos de la tarjeta
            self.tarjeta_data = api_client.get_tarjeta(self.tarjeta_codigo)
            if not self.tarjeta_data:
                messagebox.showerror("Error", "No se pudo cargar la información de la tarjeta")
                self.ventana.destroy()
                return
            
            # Obtener datos del cliente
            self.cliente_data = api_client.get_cliente(self.tarjeta_data['cliente_identificacion'])
            if not self.cliente_data:
                messagebox.showerror("Error", "No se pudo cargar la información del cliente")
                self.ventana.destroy()
                return
                
        except Exception as e:
            logger.error(f"Error al cargar datos: {e}")
            messagebox.showerror("Error", f"Error al cargar datos: {str(e)}")
            self.ventana.destroy()

    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Configurar estilo
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Section.TLabel', font=('Arial', 10, 'bold'), foreground='#2E86AB')
        style.configure('Info.TLabel', font=('Arial', 9), foreground='#666666')
        
        # Frame principal
        main_frame = ttk.Frame(self.ventana)
        main_frame.pack(fill='both', expand=True, padx=8, pady=8)
        
        # Título
        titulo = ttk.Label(main_frame, text=f"Editar Tarjeta: {self.tarjeta_codigo}", 
                          style='Title.TLabel')
        titulo.pack(pady=(0, 8))
        
        # Frame contenedor horizontal (usa grid para mejor control de tamaños)
        container = ttk.Frame(main_frame)
        container.pack(fill='both', expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(2, weight=1)
        
        # Frame izquierdo - Datos del Préstamo
        frame_left_container = ttk.Frame(container)
        frame_left_container.grid(row=0, column=0, sticky='nsew')
        frame_left_container.columnconfigure(0, weight=1)
        self.setup_seccion_prestamo(frame_left_container)
        
        # Separador vertical
        separator = ttk.Separator(container, orient='vertical')
        separator.grid(row=0, column=1, sticky='ns', padx=10, pady=5)
        
        # Frame derecho - Datos del Cliente
        frame_right_container = ttk.Frame(container)
        frame_right_container.grid(row=0, column=2, sticky='nsew')
        frame_right_container.columnconfigure(0, weight=1)
        self.setup_seccion_cliente(frame_right_container)
        
        # Frame para botones
        self.setup_botones(main_frame)

    def setup_seccion_prestamo(self, parent):
        """Configura la sección de datos del préstamo"""
        frame_prestamo = ttk.LabelFrame(parent, text="Datos del Préstamo", padding=8)
        frame_prestamo.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        
        # Número de Ruta
        ttk.Label(frame_prestamo, text="Número de Ruta (1-4 enteros):").grid(row=0, column=0, sticky='w', pady=4)
        self.entry_numero_ruta = ttk.Entry(frame_prestamo, width=18, font=('Arial', 10))
        # Validación en tiempo real: 1 a 4 enteros
        vcmd_ruta = (frame_prestamo.register(self.validar_ruta_enteros), '%P')
        self.entry_numero_ruta.configure(validate='key', validatecommand=vcmd_ruta)
        self.entry_numero_ruta.grid(row=0, column=1, sticky='ew', padx=(10, 0), pady=4)

        # Monto
        ttk.Label(frame_prestamo, text="Monto del Préstamo:").grid(row=1, column=0, sticky='w', pady=4)
        self.entry_monto = ttk.Entry(frame_prestamo, width=18, font=('Arial', 10))
        self.entry_monto.grid(row=1, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Interés
        ttk.Label(frame_prestamo, text="Interés (%):").grid(row=2, column=0, sticky='w', pady=4)
        self.entry_interes = ttk.Entry(frame_prestamo, width=18, font=('Arial', 10))
        self.entry_interes.grid(row=2, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Cuotas
        ttk.Label(frame_prestamo, text="Número de Cuotas:").grid(row=3, column=0, sticky='w', pady=4)
        self.entry_cuotas = ttk.Entry(frame_prestamo, width=18, font=('Arial', 10))
        self.entry_cuotas.grid(row=3, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Fecha de creación con calendario
        ttk.Label(frame_prestamo, text="Fecha de Creación:").grid(row=4, column=0, sticky='w', pady=4)
        self.date_entry = DateEntry(frame_prestamo, width=15, background='darkblue',
                                   foreground='white', borderwidth=2, date_pattern='dd/mm/yyyy',
                                   font=('Arial', 10))
        self.date_entry.grid(row=4, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Estado
        ttk.Label(frame_prestamo, text="Estado:").grid(row=5, column=0, sticky='w', pady=4)
        self.combo_estado = ttk.Combobox(frame_prestamo, width=15, 
                                        values=['activas', 'cancelada', 'pendiente'],
                                        state="readonly", font=('Arial', 10))
        self.combo_estado.grid(row=5, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Observaciones
        ttk.Label(frame_prestamo, text="Observaciones:").grid(row=6, column=0, sticky='nw', pady=4)
        self.text_observaciones = tk.Text(frame_prestamo, width=25, height=3, font=('Arial', 9),
                                         wrap=tk.WORD, relief='solid', borderwidth=1)
        self.text_observaciones.grid(row=6, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Separador
        ttk.Separator(frame_prestamo, orient='horizontal').grid(row=7, column=0, columnspan=2, 
                                                               sticky='ew', pady=8)
        
        # Información calculada
        ttk.Label(frame_prestamo, text="Información Calculada:", 
                 style='Section.TLabel').grid(row=8, column=0, columnspan=2, sticky='w', pady=(0, 4))
        
        # Frame para información calculada
        info_frame = ttk.Frame(frame_prestamo)
        info_frame.grid(row=9, column=0, columnspan=2, sticky='ew', pady=2)
        
        # Monto total
        ttk.Label(info_frame, text="Monto Total:", style='Info.TLabel').grid(row=0, column=0, sticky='w')
        self.lbl_monto_total = ttk.Label(info_frame, text="", foreground='#2E86AB', font=('Arial', 10, 'bold'))
        self.lbl_monto_total.grid(row=0, column=1, sticky='e')
        
        # Valor cuota
        ttk.Label(info_frame, text="Valor por Cuota:", style='Info.TLabel').grid(row=1, column=0, sticky='w')
        self.lbl_valor_cuota = ttk.Label(info_frame, text="", foreground='#2E86AB', font=('Arial', 10, 'bold'))
        self.lbl_valor_cuota.grid(row=1, column=1, sticky='e')
        
        # Configurar expansión de columnas
        frame_prestamo.columnconfigure(1, weight=1)
        info_frame.columnconfigure(1, weight=1)
        
        # (El botón de actualización individual se elimina; se usará "Guardar Cambios")
        ttk.Label(frame_prestamo, text="").grid(row=10, column=0, columnspan=2, pady=5)
        
        # Bind para calcular automáticamente
        self.entry_monto.bind('<KeyRelease>', self.calcular_valores)
        self.entry_interes.bind('<KeyRelease>', self.calcular_valores)
        self.entry_cuotas.bind('<KeyRelease>', self.calcular_valores)

    def validar_ruta_enteros(self, nuevo_valor: str):
        """Permite escribir de 1 a 4 enteros (sin decimales)."""
        if not nuevo_valor:
            return True
        if ' ' in nuevo_valor:
            return False
        return nuevo_valor.isdigit() and len(nuevo_valor) <= 4

    def _normalizar_decimal_str(self, texto: str) -> str:
        """Convierte cadenas con posibles separadores a formato Decimal estándar (###.###)."""
        if texto is None:
            return ''
        s = texto.strip()
        if not s:
            return ''
        # Si contiene ambos, asumir '.' miles y ',' decimal -> quitar puntos y cambiar coma a punto
        if '.' in s and ',' in s:
            s = s.replace('.', '').replace(',', '.')
        else:
            # Si solo hay comas, tratarlas como decimal
            s = s.replace(',', '.')
        # Quitar símbolos no numéricos salvo el punto y dígitos
        import re
        s = re.sub(r"[^0-9\.]", "", s)
        return s

    def setup_seccion_cliente(self, parent):
        """Configura la sección de datos del cliente"""
        frame_cliente = ttk.LabelFrame(parent, text="Datos del Cliente", padding=8)
        frame_cliente.grid(row=0, column=0, sticky='nsew', padx=(5, 0))
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        
        # Identificación (SOLO LECTURA - NO EDITABLE)
        ttk.Label(frame_cliente, text="Identificación:").grid(row=0, column=0, sticky='w', pady=4)
        self.lbl_identificacion = ttk.Label(frame_cliente, text="", foreground='#666666', 
                                           font=('Arial', 10), relief='solid', borderwidth=1,
                                           padding=5, background='#f0f0f0')
        self.lbl_identificacion.grid(row=0, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Advertencia sobre por qué no se puede cambiar
        warning_frame = ttk.Frame(frame_cliente)
        warning_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=2)
        
        ttk.Label(warning_frame, text="🔒 La identificación no se puede cambiar para proteger el historial", 
                 style='Info.TLabel', foreground='#d63384').pack()
        
        # Nombre
        ttk.Label(frame_cliente, text="Nombre:").grid(row=2, column=0, sticky='w', pady=4)
        self.entry_nombre = ttk.Entry(frame_cliente, width=25, font=('Arial', 10))
        self.entry_nombre.grid(row=2, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Apellido
        ttk.Label(frame_cliente, text="Apellido:").grid(row=3, column=0, sticky='w', pady=4)
        self.entry_apellido = ttk.Entry(frame_cliente, width=25, font=('Arial', 10))
        self.entry_apellido.grid(row=3, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Teléfono
        ttk.Label(frame_cliente, text="Teléfono:").grid(row=4, column=0, sticky='w', pady=4)
        self.entry_telefono = ttk.Entry(frame_cliente, width=25, font=('Arial', 10))
        self.entry_telefono.grid(row=4, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Dirección
        ttk.Label(frame_cliente, text="Dirección:").grid(row=5, column=0, sticky='nw', pady=4)
        self.text_direccion = tk.Text(frame_cliente, width=25, height=3, font=('Arial', 9),
                                     wrap=tk.WORD, relief='solid', borderwidth=1)
        self.text_direccion.grid(row=5, column=1, sticky='ew', padx=(10, 0), pady=4)
        
        # Configurar expansión de columnas
        frame_cliente.columnconfigure(1, weight=1)
        
        # (El botón de actualización individual se elimina; se usará "Guardar Cambios")
        ttk.Label(frame_cliente, text="").grid(row=6, column=0, columnspan=2, pady=2)
        
        # Separador para funciones avanzadas
        ttk.Separator(frame_cliente, orient='horizontal').grid(row=7, column=0, columnspan=2, 
                                                              sticky='ew', pady=5)
        
        # Sección de funciones avanzadas
        ttk.Label(frame_cliente, text="Funciones Avanzadas:", 
                 style='Section.TLabel').grid(row=8, column=0, columnspan=2, sticky='w', pady=(0, 2))
        
        # Botón para cambio de identificación (casos extremos)
        self.btn_cambiar_id = ttk.Button(frame_cliente, text="⚠️ Cambiar Identificación", 
                                        command=self.cambiar_identificacion_cliente)
        self.btn_cambiar_id.grid(row=9, column=0, columnspan=2, pady=2, sticky='ew')
        
        # Advertencia adicional
        ttk.Label(frame_cliente, text="Solo usar en casos de error grave en la identificación", 
                 style='Info.TLabel', foreground='red', font=('Arial', 8)).grid(row=10, column=0, columnspan=2, pady=2)

    def setup_botones(self, parent):
        """Configura los botones principales"""
        # Separador superior
        ttk.Separator(parent, orient='horizontal').pack(side='bottom', fill='x', pady=(8, 0))

        frame_botones = ttk.Frame(parent)
        frame_botones.pack(side='bottom', fill='x', pady=(8, 8))

        # Estilos más estéticos para botones
        style = ttk.Style(self.ventana)
        style.configure('Primary.TButton', font=('Arial', 10, 'bold'), padding=(10, 6), background='#4CAF50', foreground='white')
        style.configure('Cancel.TButton', font=('Arial', 10), padding=(8, 6), background='#F44336', foreground='white')
        # Hover effects
        style.map('Primary.TButton', background=[('active', '#45a049')])
        style.map('Cancel.TButton', background=[('active', '#da190b')])

        # Contenedor centrado
        center = ttk.Frame(frame_botones)
        center.pack(expand=True)
        center.columnconfigure(0, weight=1)
        center.columnconfigure(1, weight=1)

        # Botones centrados con mismo ancho visual
        btn_guardar = ttk.Button(center, text="Guardar Cambios", style='Primary.TButton',
                                 width=20, command=self.guardar_cambios_y_cerrar)
        btn_guardar.grid(row=0, column=0, padx=8)

        btn_cancelar = ttk.Button(center, text="Cancelar", style='Cancel.TButton',
                                  width=18, command=self.cancelar)
        btn_cancelar.grid(row=0, column=1, padx=8)

        # Binds para forzar mayúsculas en tiempo real
        try:
            self.entry_nombre.bind('<KeyRelease>', lambda e: self._uppercase_entry(self.entry_nombre))
            self.entry_apellido.bind('<KeyRelease>', lambda e: self._uppercase_entry(self.entry_apellido))
            self.text_direccion.bind('<KeyRelease>', lambda e: self._uppercase_text(self.text_direccion))
            self.text_observaciones.bind('<KeyRelease>', lambda e: self._uppercase_text(self.text_observaciones))
        except Exception:
            pass

    def _uppercase_entry(self, widget: ttk.Entry):
        try:
            valor = widget.get()
            nuevo = valor.upper()
            if nuevo != valor:
                pos = widget.index(tk.INSERT)
                widget.delete(0, tk.END)
                widget.insert(0, nuevo)
                widget.icursor(min(pos, len(nuevo)))
        except Exception:
            pass

    def _uppercase_text(self, widget: tk.Text):
        try:
            valor = widget.get('1.0', 'end-1c')
            nuevo = valor.upper()
            if nuevo != valor:
                idx = widget.index(tk.INSERT)
                widget.delete('1.0', tk.END)
                widget.insert('1.0', nuevo)
                widget.mark_set(tk.INSERT, idx)
        except Exception:
            pass

    def llenar_campos(self):
        """Llena los campos con los datos actuales"""
        if not self.tarjeta_data or not self.cliente_data:
            return
        
        # Datos del préstamo
        if 'numero_ruta' in self.tarjeta_data and self.tarjeta_data['numero_ruta'] is not None:
            try:
                self.entry_numero_ruta.insert(0, f"{int(float(self.tarjeta_data['numero_ruta']))}")
            except Exception:
                self.entry_numero_ruta.insert(0, str(self.tarjeta_data['numero_ruta']))
        self.entry_monto.insert(0, str(self.tarjeta_data['monto']))
        self.entry_interes.insert(0, str(self.tarjeta_data['interes']))
        self.entry_cuotas.insert(0, str(self.tarjeta_data['cuotas']))
        
        # Fecha de creación
        if self.tarjeta_data['fecha_creacion']:
            fecha = self.tarjeta_data['fecha_creacion']
            if isinstance(fecha, datetime):
                self.date_entry.set_date(fecha.date())
            else:
                # Si es string, convertir
                try:
                    fecha_obj = datetime.strptime(str(fecha), '%Y-%m-%d').date()
                    self.date_entry.set_date(fecha_obj)
                except:
                    pass
        
        self.combo_estado.set(self.tarjeta_data['estado'])
        
        if self.tarjeta_data['observaciones']:
            self.text_observaciones.insert('1.0', self.tarjeta_data['observaciones'])
        
        # Datos del cliente
        self.lbl_identificacion.config(text=self.cliente_data['identificacion'])
        self.entry_nombre.insert(0, self.cliente_data['nombre'])
        self.entry_apellido.insert(0, self.cliente_data['apellido'])
        
        if self.cliente_data['telefono']:
            self.entry_telefono.insert(0, self.cliente_data['telefono'])
        
        if self.cliente_data['direccion']:
            self.text_direccion.insert('1.0', self.cliente_data['direccion'])
        
        # Calcular valores iniciales
        self.calcular_valores()

    def calcular_valores(self, event=None):
        """Calcula y muestra los valores derivados"""
        try:
            monto_str = self._normalizar_decimal_str(self.entry_monto.get())
            interes_str = self._normalizar_decimal_str(self.entry_interes.get())
            cuotas_str = self.entry_cuotas.get().strip()
            
            if monto_str and interes_str and cuotas_str:
                monto = Decimal(monto_str)
                interes = Decimal(interes_str)
                cuotas = int(cuotas_str)
                
                # Calcular monto total
                monto_total = monto * (1 + interes / 100)
                
                # Calcular valor por cuota
                valor_cuota = monto_total / cuotas
                
                # Actualizar labels
                self.lbl_monto_total.config(text=f"${monto_total:,.0f}")
                self.lbl_valor_cuota.config(text=f"${valor_cuota:,.0f}")
            else:
                self.lbl_monto_total.config(text="")
                self.lbl_valor_cuota.config(text="")
                
        except (ValueError, ZeroDivisionError, Exception):
            self.lbl_monto_total.config(text="")
            self.lbl_valor_cuota.config(text="")

    def validar_datos_prestamo(self):
        """Valida los datos del préstamo"""
        # Validar monto
        try:
            monto = Decimal(self.entry_monto.get().strip())
            if monto <= 0:
                raise ValueError("El monto debe ser mayor a 0")
        except (ValueError, Exception):
            messagebox.showerror("Error", "El monto debe ser un número válido mayor a 0")
            return False
        
        # Validar interés
        try:
            interes = int(self.entry_interes.get().strip())
            if interes < 0 or interes > 100:
                raise ValueError("El interés debe estar entre 0 y 100")
        except (ValueError, Exception):
            messagebox.showerror("Error", "El interés debe ser un número entero entre 0 y 100")
            return False
        
        # Validar cuotas
        try:
            cuotas = int(self.entry_cuotas.get().strip())
            if cuotas <= 0:
                raise ValueError("Las cuotas deben ser mayor a 0")
        except (ValueError, Exception):
            messagebox.showerror("Error", "Las cuotas deben ser un número entero mayor a 0")
            return False
        
        return True

    def validar_datos_cliente(self):
        """Valida los datos del cliente"""
        # Validar nombre y apellido
        if not self.entry_nombre.get().strip():
            messagebox.showerror("Error", "El nombre es obligatorio")
            return False
        
        if not self.entry_apellido.get().strip():
            messagebox.showerror("Error", "El apellido es obligatorio")
            return False
        
        return True

    def actualizar_prestamo(self):
        """Actualiza solo los datos del préstamo"""
        if not self.validar_datos_prestamo():
            return
        
        try:
            # Preparar datos de la tarjeta
            monto = Decimal(self._normalizar_decimal_str(self.entry_monto.get()))
            interes = int(self.entry_interes.get().strip())
            cuotas = int(self.entry_cuotas.get().strip())
            fecha_creacion = datetime.combine(self.date_entry.get_date(), datetime.min.time())
            observaciones = self.text_observaciones.get('1.0', 'end-1c').strip()
            numero_ruta_raw = self.entry_numero_ruta.get().strip()
            numero_ruta = None
            if numero_ruta_raw:
                if not numero_ruta_raw.isdigit() or not (1 <= len(numero_ruta_raw) <= 4):
                    messagebox.showerror("Error", "Número de ruta inválido. Debe ser un entero de 1 a 4 dígitos")
                    return
                numero_ruta = int(numero_ruta_raw)
            
            # Actualizar tarjeta
            resp = api_client.update_tarjeta(self.tarjeta_codigo, {
                'monto': float(monto),
                'cuotas': int(cuotas),
                'fecha_creacion': fecha_creacion,
                'interes': int(interes),
                'observaciones': observaciones or None,
                'numero_ruta': numero_ruta
            })
            exito_tarjeta = bool(resp and resp.get('codigo') == self.tarjeta_codigo)
            
            if not exito_tarjeta:
                messagebox.showerror("Error", "No se pudo actualizar los datos del préstamo")
                return
            
            # Actualizar estado si cambió
            estado_actual = self.combo_estado.get()
            if estado_actual != self.tarjeta_data['estado']:
                api_client.update_tarjeta(self.tarjeta_codigo, {'estado': estado_actual})
            
            messagebox.showinfo("Éxito", "Los datos del préstamo han sido actualizados correctamente")
            
            # Actualizar la vista principal
            if hasattr(self.parent, 'mostrar_tabla_tarjetas'):
                self.parent.mostrar_tabla_tarjetas()
                
        except Exception as e:
            logger.error(f"Error al actualizar préstamo: {e}")
            messagebox.showerror("Error", f"Error al actualizar préstamo: {str(e)}")

    def actualizar_cliente(self):
        """Actualiza solo los datos del cliente"""
        if not self.validar_datos_cliente():
            return
        
        try:
            # Preparar datos del cliente
            nombre = self.entry_nombre.get().strip()
            apellido = self.entry_apellido.get().strip()
            telefono = self.entry_telefono.get().strip() or None
            direccion = self.text_direccion.get('1.0', 'end-1c').strip() or None
            
            # Actualizar cliente
            resp = api_client.update_cliente(self.cliente_data['identificacion'], {
                'nombre': nombre,
                'apellido': apellido,
                'telefono': telefono,
                'direccion': direccion
            })
            exito_cliente = bool(resp and resp.get('identificacion') == self.cliente_data['identificacion'])
            
            if not exito_cliente:
                messagebox.showerror("Error", "No se pudo actualizar los datos del cliente")
                return
            
            messagebox.showinfo("Éxito", "Los datos del cliente han sido actualizados correctamente")
            
            # Actualizar la vista principal
            if hasattr(self.parent, 'mostrar_tabla_tarjetas'):
                self.parent.mostrar_tabla_tarjetas()
                
        except Exception as e:
            logger.error(f"Error al actualizar cliente: {e}")
            messagebox.showerror("Error", f"Error al actualizar cliente: {str(e)}")

    def actualizar_todo(self):
        """Actualiza tanto el préstamo como el cliente"""
        if not self.validar_datos_prestamo() or not self.validar_datos_cliente():
            return
        
        # Actualizar préstamo
        self.actualizar_prestamo()
        
        # Actualizar cliente
        self.actualizar_cliente()
        
        # Cerrar ventana después de actualizar todo
        self.ventana.destroy()

    def guardar_cambios_y_cerrar(self):
        """Consolida la actualización de cliente y préstamo y cierra la ventana al final."""
        if not self.validar_datos_prestamo() or not self.validar_datos_cliente():
            return
        # Intentar ambos; si cualquiera falla, mostrar error y no cerrar
        try:
            self.actualizar_prestamo()
            self.actualizar_cliente()
            self.ventana.destroy()
        except Exception as e:
            logger.error(f"Error al guardar cambios consolidados: {e}")
            messagebox.showerror("Error", f"No se pudieron guardar todos los cambios: {str(e)}")

    def cancelar(self):
        """Cancela la edición y cierra la ventana"""
        respuesta = messagebox.askyesno("Confirmar", 
                                       "¿Está seguro de que desea cancelar? Los cambios no guardados se perderán.")
        if respuesta:
            self.ventana.destroy()

    def cambiar_identificacion_cliente(self):
        """Función para cambiar la identificación del cliente en casos extremos"""
        # Múltiples advertencias y confirmaciones
        respuesta1 = messagebox.askyesno(
            "⚠️ ADVERTENCIA CRÍTICA",
            "¿Está ABSOLUTAMENTE SEGURO de que necesita cambiar la identificación?\n\n"
            "ESTO PUEDE CAUSAR:\n"
            "• Pérdida del historial de tarjetas\n"
            "• Pérdida del historial de abonos\n"
            "• Problemas en reportes y estadísticas\n"
            "• Inconsistencias en la base de datos\n\n"
            "¿Continuar de todos modos?"
        )
        
        if not respuesta1:
            return
        
        # Segunda confirmación
        respuesta2 = messagebox.askyesno(
            "🔴 ÚLTIMA ADVERTENCIA",
            "Esta acción es IRREVERSIBLE y puede dañar permanentemente los datos.\n\n"
            "¿Está 100% seguro de que quiere continuar?\n\n"
            "Recomendamos contactar al administrador del sistema antes de proceder."
        )
        
        if not respuesta2:
            return
        
        # Solicitar nueva identificación
        nueva_identificacion = simpledialog.askstring(
            "Nueva Identificación",
            f"Identificación actual: {self.cliente_data['identificacion']}\n\n"
            "Ingrese la nueva identificación:",
            parent=self.ventana
        )
        
        if not nueva_identificacion or nueva_identificacion.strip() == "":
            messagebox.showwarning("Cancelado", "Operación cancelada: No se ingresó una identificación válida")
            return
        
        nueva_identificacion = nueva_identificacion.strip()
        
        # Verificar que la nueva identificación no exista
        cliente_existente = None
        try:
            cliente_existente = api_client.get_cliente(nueva_identificacion)
        except Exception:
            cliente_existente = None
        if cliente_existente:
            messagebox.showerror("Error", f"Ya existe un cliente con la identificación '{nueva_identificacion}'")
            return
        
        # Confirmación final con resumen
        respuesta_final = messagebox.askyesno(
            "Confirmación Final",
            f"RESUMEN DEL CAMBIO:\n\n"
            f"Identificación actual: {self.cliente_data['identificacion']}\n"
            f"Nueva identificación: {nueva_identificacion}\n\n"
            f"Cliente: {self.cliente_data['nombre']} {self.cliente_data['apellido']}\n\n"
            "¿Proceder con el cambio?"
        )
        
        if not respuesta_final:
            return
        
        try:
            # Aquí implementarías la lógica compleja para cambiar la identificación
            # Esto requeriría:
            # 1. Crear nuevo cliente con nueva identificación
            # 2. Actualizar todas las tarjetas para apuntar al nuevo cliente
            # 3. Verificar que todos los abonos sigan funcionando
            # 4. Eliminar el cliente anterior
            
            messagebox.showinfo(
                "Función No Implementada",
                "Esta función requiere implementación especializada.\n\n"
                "Por seguridad, contacte al administrador del sistema.\n\n"
                "Se recomienda:\n"
                "1. Hacer backup de la base de datos\n"
                "2. Implementar migración de datos\n"
                "3. Verificar integridad después del cambio"
            )
            
        except Exception as e:
            logger.error(f"Error en cambio de identificación: {e}")
            messagebox.showerror("Error Crítico", f"Error durante el cambio: {str(e)}") 