import tkinter as tk
from tkinter import ttk, messagebox
from decimal import Decimal
import logging
import decimal
from api_client.client import api_client
from ventanas.solicitar_documento import VentanaSolicitarDocumento

logger = logging.getLogger(__name__)

class VentanaNuevaTarjeta(tk.Toplevel):
    def __init__(self, parent, cliente=None, documento=None):
        super().__init__(parent)
        self.parent = parent
        self.cliente = cliente
        self.documento = documento
        self.empleado_identificacion = self.obtener_empleado_id()
        
        # Configurar ventana
        self.title("Nueva Tarjeta")
        
        # Ajustar tamaño y posición inicial
        ancho = "600"
        alto = "560"
        x = (self.winfo_screenwidth() - int(ancho)) // 2
        y = (self.winfo_screenheight() - int(alto)) // 2
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        
        self.resizable(False, False)
        
        # Hacer la ventana modal
        self.transient(parent)
        self.grab_set()
        
        # Configurar la interfaz
        self.setup_ui_solicitar_documento()
        
        # Si hay cliente, pre-llenar los campos
        if self.cliente:
            self.pre_llenar_datos_cliente()
    
    def pre_llenar_datos_cliente(self):
        """Pre-llena los campos con los datos del cliente"""
        self.entry_nombre.insert(0, self.cliente['nombre'])
        self.entry_nombre.config(state='disabled')
        
        self.entry_apellido.insert(0, self.cliente['apellido'])
        self.entry_apellido.config(state='disabled')
        
        self.entry_id.insert(0, self.cliente['identificacion'])
        self.entry_id.config(state='disabled')
        
        if self.cliente.get('telefono'):
            self.entry_telefono.insert(0, self.cliente['telefono'])
            self.entry_telefono.config(state='disabled')
            
        if self.cliente.get('direccion'):
            self.entry_direccion.insert(0, self.cliente['direccion'])
            self.entry_direccion.config(state='disabled')
        
        # Enfocar el campo de monto
        self.entry_monto.focus()

    def validar_longitud(self, valor, longitud):
        """Valida que la longitud del texto no exceda el límite"""
        return len(valor) <= int(longitud)

    def setup_ui_solicitar_documento(self):
        """Configura la interfaz para solicitar documento"""
        # Registrar validadores de longitud
        vcmd_20 = (self.register(lambda P: self.validar_longitud(P, 20)), '%P')
        vcmd_40 = (self.register(lambda P: self.validar_longitud(P, 40)), '%P')
        vcmd_200 = (self.register(lambda P: self.validar_longitud(P, 200)), '%P')

        # Frame principal sin padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True)
        
        # Frame superior para los formularios con padding
        forms_frame = ttk.Frame(main_frame, padding="20")
        forms_frame.pack(fill='both', expand=True)
        
        # Frame izquierdo para datos del cliente
        frame_cliente = ttk.LabelFrame(forms_frame, text="Datos del Cliente", padding="10")
        frame_cliente.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        campos_cliente = [
            ("Nombre", 'entry_nombre', vcmd_40),
            ("Apellido", 'entry_apellido', vcmd_40),
            ("Identificación", 'entry_id', vcmd_20),
            ("Teléfono", 'entry_telefono', vcmd_20),
            ("Dirección", 'entry_direccion', vcmd_200)
        ]
        
        for label_text, entry_name, vcmd in campos_cliente:
            ttk.Label(frame_cliente, text=label_text).pack(anchor='w', pady=(5,0))
            entry = ttk.Entry(frame_cliente, width=30, validate='key', validatecommand=vcmd)
            entry.pack(fill='x', pady=(2,5))
            setattr(self, entry_name, entry)

        # Binds para forzar mayúsculas en tiempo real en entradas de cliente
        try:
            self.entry_nombre.bind('<KeyRelease>', lambda e: self._uppercase_entry(self.entry_nombre))
            self.entry_apellido.bind('<KeyRelease>', lambda e: self._uppercase_entry(self.entry_apellido))
            self.entry_direccion.bind('<KeyRelease>', lambda e: self._uppercase_entry(self.entry_direccion))
        except Exception:
            pass
        
        if self.documento:
            self.entry_id.insert(0, self.documento)
            self.entry_id.config(state='readonly')
        
        # Frame derecho para datos de la tarjeta
        frame_tarjeta = ttk.LabelFrame(forms_frame, text="Datos de la Tarjeta", padding="10")
        frame_tarjeta.pack(side='right', fill='both', expand=True)
        
        # Frame para número de ruta con más espacio
        frame_ruta = ttk.Frame(frame_tarjeta)
        frame_ruta.pack(fill='x', pady=(5,10))
        
        ttk.Label(frame_ruta, text="Número de Ruta (1-4 enteros):").pack(side='left')
        self.entry_ruta = ttk.Entry(frame_ruta, width=6)
        # Validación en tiempo real: 1 a 4 dígitos enteros
        vcmd_ruta = (self.register(self.validar_ruta_enteros), '%P')
        self.entry_ruta.configure(validate='key', validatecommand=vcmd_ruta)
        self.entry_ruta.pack(side='left', padx=10)
        
        # Frame separado para el checkbox
        frame_checkbox = ttk.Frame(frame_tarjeta)
        frame_checkbox.pack(fill='x', pady=(0,10))
        
        self.var_insertar_antes = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame_checkbox, 
                        text="Insertar antes de la selección", 
                        variable=self.var_insertar_antes).pack(anchor='w')
        
        # Frame para campos de la tarjeta
        ttk.Label(frame_tarjeta, text="Monto").pack(anchor='w', pady=(10,0))
        frame_monto = ttk.Frame(frame_tarjeta)
        frame_monto.pack(fill='x', pady=(5,10))
        ttk.Label(frame_monto, text="$").pack(side='left')
        self.entry_monto = ttk.Entry(frame_monto, width=13)  # Para 9 dígitos + puntos
        self.entry_monto.pack(side='left', padx=5)
        self.entry_monto.bind('<KeyRelease>', self.formatear_monto)
        
        ttk.Label(frame_tarjeta, text="Interés (%)").pack(anchor='w', pady=(10,0))
        self.combo_interes = ttk.Combobox(frame_tarjeta, 
                                         values=['5','10','15','20','25','30'],
                                         state='readonly', width=5)
        self.combo_interes.pack(anchor='w', pady=(5,10))
        self.combo_interes.set('20')  # Establecer 20% por defecto
        
        ttk.Label(frame_tarjeta, text="Modalidad / Cuotas").pack(anchor='w', pady=(10,0))
        frame_mod_cuotas = ttk.Frame(frame_tarjeta)
        frame_mod_cuotas.pack(fill='x', pady=(5,10))
        # Combobox modalidad (por defecto: diario)
        self.combo_modalidad = ttk.Combobox(
            frame_mod_cuotas,
            values=['diario', 'semanal', 'quincenal', 'mensual'],
            state='readonly',
            width=10
        )
        self.combo_modalidad.pack(side='left')
        self.combo_modalidad.set('diario')
        # Entry cuotas (más corto para dejar espacio al combobox)
        self.entry_cuotas = ttk.Entry(frame_mod_cuotas, width=6)
        self.entry_cuotas.pack(side='left', padx=(8, 0))
        self.entry_cuotas.insert(0, '30')  # Establecer 30 cuotas por defecto
        self.entry_cuotas.bind('<FocusIn>', self.seleccionar_cuotas)  # Agregar evento de foco
        
        ttk.Label(frame_tarjeta, text="Observaciones").pack(anchor='w', pady=(10,0))
        self.entry_observaciones = tk.Text(frame_tarjeta, width=30, height=3)
        self.entry_observaciones.pack(fill='x', pady=(5,10))
        # Limitar caracteres en observaciones a 500 (antes 30)
        self.entry_observaciones.bind('<KeyPress>', lambda e: self.limitar_observaciones(e, 500))
        # Mayúsculas en tiempo real para observaciones
        self.entry_observaciones.bind('<KeyRelease>', lambda e: self._uppercase_text(self.entry_observaciones))
        
        # Frame inferior para los botones
        frame_botones = ttk.Frame(self, padding="10")
        frame_botones.pack(side='bottom', fill='x')
        # Asegurar visibilidad de botones con tamaño mínimo
        try:
            self.update_idletasks()
            self.minsize(600, 560)
        except Exception:
            pass
        
        # Frame contenedor para centrar los botones
        frame_centro = ttk.Frame(frame_botones)
        frame_centro.pack(expand=True)
        
        # Botones más robustos y centrados
        ttk.Button(frame_centro, 
                   text="CREAR",
                   width=12,      # Un poco más angosto
                   padding=5,      # Más alto
                   command=self.crear).pack(side='left', padx=5, pady=5)
        
        ttk.Button(frame_centro, 
                   text="CANCELAR",
                   width=12,      # Un poco más angosto
                   padding=5,     # Más alto
                   command=self.destroy).pack(side='left', padx=5, pady=5)
    
    def validar_numeros(self, nuevo_valor):
        """Valida que solo se ingresen números"""
        if not nuevo_valor:  # Permitir borrar
            return True
        return nuevo_valor.isdigit()

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

    def formatear_monto(self, event=None):
        """Formatea el monto con puntos de mil mientras se escribe"""
        texto = self.entry_monto.get().replace(".", "")  # Quitar puntos existentes
        if texto and texto.isdigit():
            # Formatear con puntos de mil
            numero = int(texto)
            texto_formateado = "{:,}".format(numero).replace(",", ".")
            # Actualizar entry sin activar el evento
            self.entry_monto.delete(0, tk.END)
            self.entry_monto.insert(0, texto_formateado)

    def limitar_observaciones(self, event, limit=30):
        """Limita el texto de observaciones al límite especificado"""
        # Permitir teclas de control (backspace, delete, etc.)
        if len(event.char) == 0:
            return
        
        texto_actual = self.entry_observaciones.get("1.0", "end-1c")
        if len(texto_actual) >= limit:
            return "break"  # Evita que se escriba el carácter

    def validar_monto(self, nuevo_valor):
        """Valida que el monto solo contenga números y puntos"""
        if not nuevo_valor:  # Permitir borrar
            return True
        # Quitar puntos para validar
        valor_sin_puntos = nuevo_valor.replace(".", "")
        # Verificar que sean solo números y no más de 8 dígitos
        return valor_sin_puntos.isdigit() and len(valor_sin_puntos) <= 8

    def validar_ruta_enteros(self, nuevo_valor: str):
        """Permite escribir de 1 a 4 enteros (sin decimales)."""
        if not nuevo_valor:
            return True
        if ' ' in nuevo_valor:
            return False
        return nuevo_valor.isdigit() and len(nuevo_valor) <= 4

    def obtener_empleado_id(self):
        """Obtiene la identificación del empleado seleccionado"""
        try:
            empleado_seleccionado = self.parent.combo_empleados.get()
            if empleado_seleccionado in self.parent.empleados_dict:
                return self.parent.empleados_dict[empleado_seleccionado]  # Retorna la identificación (string)
            return None
        except Exception as e:
            logger.error(f"Error al obtener identificación del empleado: {e}")
            return None

    def crear(self):
        """Crear nuevo cliente y tarjeta"""
        try:
            # 1. Validar campos obligatorios del cliente
            errores = []
            
            # Validar campos del cliente
            nombre = self.entry_nombre.get().strip() if hasattr(self, 'entry_nombre') else self.cliente['nombre']
            if not nombre:
                errores.append("El nombre del cliente es obligatorio")
                
            apellido = self.entry_apellido.get().strip() if hasattr(self, 'entry_apellido') else self.cliente['apellido']
            if not apellido:
                errores.append("El apellido del cliente es obligatorio")
                
            identificacion = self.entry_id.get().strip() if hasattr(self, 'entry_id') else self.cliente['identificacion']
            if not identificacion:
                errores.append("La identificación del cliente es obligatoria")

            # Validar campos de la tarjeta
            try:
                monto_texto = self.entry_monto.get().strip().replace(".", "")
                if not monto_texto:
                    errores.append("El monto es obligatorio")
                else:
                    monto = Decimal(monto_texto)
                    if monto <= 0:
                        errores.append("El monto debe ser mayor a 0")
            except (ValueError, decimal.InvalidOperation):
                errores.append("El monto debe ser un número válido")

            try:
                if not self.combo_interes.get():
                    errores.append("El interés es obligatorio")
                else:
                    interes = int(self.combo_interes.get())
                    if interes < 0:
                        errores.append("El interés no puede ser negativo")
            except ValueError:
                errores.append("El interés debe ser un número válido")

            try:
                cuotas_texto = self.entry_cuotas.get().strip()
                if not cuotas_texto:
                    errores.append("El número de cuotas es obligatorio")
                else:
                    cuotas = int(cuotas_texto)
                    if cuotas <= 0:
                        errores.append("El número de cuotas debe ser mayor a 0")
            except ValueError:
                errores.append("El número de cuotas debe ser un número válido")

            modalidad_pago = 'diario'
            try:
                modalidad_pago = str(self.combo_modalidad.get() or 'diario').strip().lower()
                if modalidad_pago not in ('diario', 'semanal', 'quincenal', 'mensual'):
                    modalidad_pago = 'diario'
            except Exception:
                modalidad_pago = 'diario'

            # Si hay errores, mostrarlos y detener la creación
            if errores:
                messagebox.showerror("Error de Validación", "\n".join(errores))
                return

            # Obtener campos opcionales
            telefono = self.entry_telefono.get().strip() if hasattr(self, 'entry_telefono') else None
            direccion = self.entry_direccion.get().strip() if hasattr(self, 'entry_direccion') else None
            ruta = self.entry_ruta.get().strip() if hasattr(self, 'entry_ruta') else None
            observaciones = self.entry_observaciones.get("1.0", tk.END).strip() if hasattr(self, 'entry_observaciones') else None

            # 2. Validar que tengamos el empleado_identificacion
            if not self.empleado_identificacion:
                messagebox.showerror("Error", "No se pudo obtener la identificación del empleado")
                return

            # 3. Crear cliente solo si es nuevo y no existe
            if not self.cliente and hasattr(self, 'entry_nombre'):  # Si es cliente nuevo
                # Verificar una vez más que el cliente no exista
                try:
                    cliente_existente = api_client.get_cliente(identificacion)
                except Exception:
                    cliente_existente = None
                if cliente_existente and isinstance(cliente_existente, dict) and cliente_existente.get('identificacion'):
                    self.cliente = cliente_existente
                else:
                    nuevo_cliente = api_client.create_cliente({
                        'identificacion': identificacion,
                        'nombre': nombre,
                        'apellido': apellido,
                        'telefono': telefono,
                        'direccion': direccion
                    })
                    if not (isinstance(nuevo_cliente, dict) and nuevo_cliente.get('identificacion') == identificacion):
                        messagebox.showerror("Error", "No se pudo crear el cliente")
                        return

            # Manejar el número de ruta
            numero_ruta = None 
            posicion_anterior = None
            posicion_siguiente = None

            # Verificar si hay ruta manual
            # Ruta manual como entero (1 a 4 dígitos)
            ruta_manual = self.entry_ruta.get().strip()
            logger.debug(f"Ruta manual ingresada: {ruta_manual}")
            
            if ruta_manual:
                try:
                    if not ruta_manual.isdigit() or not (1 <= len(ruta_manual) <= 4):
                        messagebox.showerror("Error", "La ruta debe ser un entero de 1 a 4 dígitos (ej: 100, 2500)")
                        return
                    numero_ruta = Decimal(int(ruta_manual))
                    logger.debug(f"Número de ruta asignado: {numero_ruta}")
                except decimal.InvalidOperation:
                    messagebox.showerror("Error", "El número de ruta debe ser un número decimal válido")
                    return

            # Si no hay ruta manual, calcular basado en la selección
            seleccion = self.parent.tree.selection()
            if seleccion and not ruta_manual:
                item = self.parent.tree.item(seleccion[0])
                # Obtener la parte numérica de la ruta formateada (ej: "123.456")
                ruta_str = item['values'][0]
                ruta_actual = Decimal(ruta_str)
                logger.debug(f"Ruta de la tarjeta seleccionada: {ruta_actual}")
                
                if self.var_insertar_antes.get():
                    posicion_siguiente = ruta_actual
                    logger.debug(f"Insertando antes de la ruta {ruta_actual}")
                else:
                    posicion_anterior = ruta_actual
                    logger.debug(f"Insertando después de la ruta {ruta_actual}")

            # Crear tarjeta vía API
            nueva_tarjeta = api_client.create_tarjeta({
                'cliente_identificacion': identificacion,
                'empleado_identificacion': self.empleado_identificacion,
                'monto': float(monto),
                'cuotas': int(cuotas),
                'interes': int(interes),
                'modalidad_pago': modalidad_pago,
                'numero_ruta': float(numero_ruta) if numero_ruta is not None else None,
                'observaciones': observaciones or None,
                'posicion_anterior': float(posicion_anterior) if posicion_anterior is not None else None,
                'posicion_siguiente': float(posicion_siguiente) if posicion_siguiente is not None else None
            })
            if not (isinstance(nueva_tarjeta, dict) and nueva_tarjeta.get('codigo')):
                messagebox.showerror("Error", "No se pudo crear la tarjeta")
                return
                
            messagebox.showinfo("Éxito", "Cliente y tarjeta creados correctamente")
            
            # El parent ES el frame_entrega, no necesitamos buscar un atributo
            # Destruir esta ventana
           
            # Actualizar el TreeView directamente en el parent (que es FrameEntrega)
            self.parent.actualizar_vista_nueva_tarjeta(nueva_tarjeta['codigo'])

            self.destroy()


        except Exception as e:
            logger.error(f"Error inesperado al crear cliente y tarjeta: {str(e)}")
            messagebox.showerror("Error", f"Error inesperado al crear cliente y tarjeta: {str(e)}")

    def obtener_posicion(self):
        """Obtiene la posición donde se insertará la tarjeta"""
        selected_item = self.parent.frame_tabla.selection()
        if not selected_item:
            return 'end'
        
        current_index = self.parent.frame_tabla.index(selected_item)
        return current_index if self.var_insertar_antes.get() else current_index + 1 

    def seleccionar_cuotas(self, event):
        """Selecciona todo el contenido del entry de cuotas"""
        event.widget.select_range(0, tk.END)
        event.widget.icursor(tk.END)  # Coloca el cursor al final

    def verificar_documento(self):
        """Verifica si el cliente existe y abre la ventana correspondiente"""
        documento = self.entry_documento.get().strip()
        if not documento:
            messagebox.showwarning("Advertencia", "Por favor ingrese un documento")
            return
            
        try:
            cliente = api_client.get_cliente(documento)
        except Exception:
            cliente = None
        if cliente:
            # Cliente existente
            self.cliente = cliente
            self.destroy()
            VentanaNuevaTarjeta(self.parent, cliente=cliente)
        else:
            # Cliente nuevo
            self.destroy()
            VentanaSolicitarDocumento(self.parent, documento)

    