import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkcalendar import Calendar, DateEntry
from datetime import datetime, timedelta
from api_client.client import APIError, api_client
from decimal import Decimal

# --- Ventana Emergente para Manejar Eliminación de Empleados ---
class VentanaEliminarEmpleado(tk.Toplevel):
    """Ventana para manejar la eliminación de empleados con diferentes opciones."""
    def __init__(self, parent, callback_actualizar, api_client, empleado_data):
        super().__init__(parent)
        self.callback_actualizar = callback_actualizar
        self.api_client = api_client
        self.empleado_data = empleado_data
        self.empleados_disponibles = []

        self.title(f"Eliminar Empleado: {empleado_data['nombre_completo']}")
        self.geometry("650x600")
        self.resizable(False, False)
        self.grab_set() # Hacer la ventana modal
        
        # Centralizar la ventana en la pantalla
        self.center_window()

        self.setup_styles()
        self.setup_ui()
        self.cargar_empleados_disponibles()

    def center_window(self):
        """Centra la ventana en la pantalla."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def setup_styles(self):
        style = ttk.Style(self)
        style.configure('TLabel', font=('Arial', 10))
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Warning.TLabel', font=('Arial', 10, 'bold'), foreground='red')
        style.configure('Info.TLabel', font=('Arial', 9), foreground='blue')
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))
        style.configure('Danger.TButton', font=('Arial', 10, 'bold'), foreground='white', background='red')
        style.configure('Success.TButton', font=('Arial', 10, 'bold'), foreground='white', background='green')

    def setup_ui(self):
        # Contenedor con desplazamiento vertical para asegurar que todo el contenido sea accesible
        container = ttk.Frame(self)
        container.pack(fill='both', expand=True)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        self.main_frame = ttk.Frame(canvas, padding="20")
        canvas_window = canvas.create_window((0, 0), window=self.main_frame, anchor='nw')

        def on_frame_configure(event):
            # Ajustar el área de scroll al contenido
            canvas.configure(scrollregion=canvas.bbox('all'))

        def on_canvas_configure(event):
            # Hacer que el frame interno tenga el mismo ancho que el canvas
            canvas.itemconfigure(canvas_window, width=event.width)

        self.main_frame.bind('<Configure>', on_frame_configure)
        canvas.bind('<Configure>', on_canvas_configure)

        # Título
        ttk.Label(self.main_frame, text="🗑️ Eliminar Empleado", style='Header.TLabel').pack(pady=(0, 15))
        
        # Información del empleado
        info_frame = ttk.LabelFrame(self.main_frame, text="Información del Empleado", padding="10")
        info_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(info_frame, text=f"👤 Nombre: {self.empleado_data['nombre_completo']}").pack(anchor='w')
        ttk.Label(info_frame, text=f"🆔 Identificación: {self.empleado_data['identificacion']}").pack(anchor='w')
        ttk.Label(info_frame, text=f"📞 Teléfono: {self.empleado_data.get('telefono', 'N/A')}").pack(anchor='w')
        ttk.Label(info_frame, text=f"🏠 Dirección: {self.empleado_data.get('direccion', 'N/A')}").pack(anchor='w')

        # Verificar si tiene tarjetas
        self.verificar_tarjetas()

    def verificar_tarjetas(self):
        """Verifica si el empleado tiene datos relacionados que impiden borrado directo."""
        try:
            # Intentar eliminar para ver si tiene dependencias
            self.api_client.delete_empleado(self.empleado_data['identificacion'])
            # Si llegamos aquí, no tenía dependencias
            self.mostrar_eliminacion_simple()
        except APIError as e:
            # Si la API devuelve 409 (conflicto por dependencias), mostrar opciones
            if getattr(e, 'status_code', None) == 409:
                self.mostrar_opciones_con_tarjetas("conflicto 409 - dependencias")
            else:
                messagebox.showerror("Error", f"Error de API al verificar empleado:\n{e.message}", parent=self)
                self.destroy()
        except Exception as e:
            error_message = str(e)
            if ("tarjetas asociadas" in error_message.lower() or
                "foreign key" in error_message.lower() or
                "datos relacionados" in error_message.lower() or
                "409" in error_message):
                # Tiene dependencias, mostrar opciones
                self.mostrar_opciones_con_tarjetas(error_message)
            else:
                # Otro error
                messagebox.showerror("Error", f"Error al verificar empleado:\n{e}", parent=self)
                self.destroy()

    def mostrar_eliminacion_simple(self):
        """Muestra la interfaz para eliminación simple (sin tarjetas)."""
        main_frame = self.main_frame
        
        # Mensaje de confirmación
        confirm_frame = ttk.LabelFrame(main_frame, text="Confirmación", padding="10")
        confirm_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(confirm_frame, text="✅ Este empleado no tiene tarjetas asociadas.", 
                 style='Info.TLabel').pack(anchor='w')
        ttk.Label(confirm_frame, text="Puede ser eliminado sin problemas.", 
                 style='Info.TLabel').pack(anchor='w')
        
        # Botones
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(btn_frame, text="✅ Eliminar Empleado", style='Danger.TButton', 
                  command=self.eliminar_empleado_simple).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="✖ Cancelar", command=self.destroy).pack(side='right')

    def mostrar_opciones_con_tarjetas(self, error_message):
        """Muestra las opciones cuando el empleado tiene tarjetas asociadas."""
        main_frame = self.main_frame
        
        # Mensaje de advertencia
        warning_frame = ttk.LabelFrame(main_frame, text="⚠️ Advertencia", padding="10")
        warning_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(warning_frame, text="❌ Este empleado tiene tarjetas asociadas.", 
                 style='Warning.TLabel').pack(anchor='w')
        ttk.Label(warning_frame, text="No se puede eliminar directamente.", 
                 style='Warning.TLabel').pack(anchor='w')
        
        # Opciones disponibles
        options_frame = ttk.LabelFrame(main_frame, text="Opciones Disponibles", padding="10")
        options_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # Opción 1: Transferir tarjetas
        ttk.Label(options_frame, text="1️⃣ Transferir todas las tarjetas a otro empleado:", 
                 font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        
        transfer_frame = ttk.Frame(options_frame)
        transfer_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(transfer_frame, text="Empleado destino:").pack(side='left')
        self.combo_empleado_destino = ttk.Combobox(transfer_frame, width=30, state='readonly')
        self.combo_empleado_destino.pack(side='left', padx=(5, 10))
        
        ttk.Button(transfer_frame, text="🔄 Transferir", style='Action.TButton',
                  command=self.transferir_tarjetas).pack(side='left')
        
        # Separador visual
        ttk.Separator(options_frame, orient='horizontal').pack(fill='x', pady=15)
        
        # Opción 2: Eliminación forzada
        ttk.Label(options_frame, text="2️⃣ Eliminación forzada (elimina empleado y todas sus tarjetas):", 
                 font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        
        ttk.Label(options_frame, text="⚠️ ADVERTENCIA: Esta acción es IRREVERSIBLE y eliminará:", 
                 style='Warning.TLabel').pack(anchor='w')
        ttk.Label(options_frame, text="   • Todas las tarjetas del empleado", 
                 style='Warning.TLabel').pack(anchor='w')
        ttk.Label(options_frame, text="   • Todos los abonos asociados", 
                 style='Warning.TLabel').pack(anchor='w')
        ttk.Label(options_frame, text="   • El empleado", 
                 style='Warning.TLabel').pack(anchor='w')
        
        # Frame para la eliminación forzada con mejor visibilidad
        force_frame = ttk.LabelFrame(options_frame, text="Eliminación Forzada", padding="10")
        force_frame.pack(fill='x', pady=(10, 0))
        
        self.var_confirmar_eliminacion = tk.BooleanVar()
        checkbox = ttk.Checkbutton(force_frame, text="☑️ Confirmo que entiendo las consecuencias", 
                       variable=self.var_confirmar_eliminacion)
        checkbox.pack(anchor='w', pady=(0, 10))
        
        # Botón de eliminación forzada más visible
        btn_eliminar_todo = tk.Button(force_frame, 
                                     text="💥 ELIMINAR EMPLEADO Y TODAS SUS TARJETAS", 
                                     font=('Arial', 12, 'bold'),
                                     bg='red', fg='white',
                                     relief='raised', bd=3,
                                     command=self.eliminar_forzado)
        btn_eliminar_todo.pack(anchor='w', fill='x', pady=(5, 0))
        
        # Mensaje adicional
        ttk.Label(force_frame, text="⚠️ Esta acción NO se puede deshacer", 
                 style='Warning.TLabel', font=('Arial', 9, 'italic')).pack(anchor='w', pady=(5, 0))
        
        # Botón cancelar
        ttk.Button(self.main_frame, text="✖ Cancelar", command=self.destroy).pack(pady=(10, 0))
        
        # Cargar empleados destino ahora que el combobox existe
        try:
            self.cargar_empleados_disponibles()
        except Exception:
            pass

    def cargar_empleados_disponibles(self):
        """Carga la lista de empleados disponibles para transferencia."""
        try:
            empleados = self.api_client.list_empleados()
            # Filtrar el empleado actual
            self.empleados_disponibles = [
                emp for emp in empleados 
                if emp['identificacion'] != self.empleado_data['identificacion']
            ]
            
            # Actualizar combobox si existe
            if hasattr(self, 'combo_empleado_destino'):
                nombres = [f"{emp['nombre_completo']} ({emp['identificacion']})" 
                          for emp in self.empleados_disponibles]
                self.combo_empleado_destino['values'] = nombres
                if nombres:
                    self.combo_empleado_destino.current(0)
                else:
                    # Si no hay empleados disponibles, mostrar mensaje
                    self.combo_empleado_destino['values'] = ["No hay empleados disponibles"]
                    self.combo_empleado_destino.current(0)
        except Exception as e:
            print(f"Error al cargar empleados: {e}")  # Debug
            messagebox.showerror("Error", f"No se pudieron cargar los empleados:\n{e}", parent=self)

    def transferir_tarjetas(self):
        """Transfiere las tarjetas del empleado a otro empleado."""
        if not hasattr(self, 'combo_empleado_destino'):
            return
            
        seleccion = self.combo_empleado_destino.get()
        if not seleccion:
            messagebox.showwarning("Selección Requerida", "Seleccione un empleado destino.", parent=self)
            return
        
        # Extraer identificación del empleado destino
        empleado_destino = None
        for emp in self.empleados_disponibles:
            if f"{emp['nombre_completo']} ({emp['identificacion']})" == seleccion:
                empleado_destino = emp
                break
        
        if not empleado_destino:
            messagebox.showerror("Error", "Empleado destino no encontrado.", parent=self)
            return
        
        # Confirmar transferencia
        if not messagebox.askyesno("Confirmar Transferencia", 
                                  f"¿Está seguro de transferir todas las tarjetas de "
                                  f"{self.empleado_data['nombre_completo']} a "
                                  f"{empleado_destino['nombre_completo']}?", parent=self):
            return
        
        try:
            # Realizar transferencia
            self.api_client.transferir_tarjetas_empleado(
                self.empleado_data['identificacion'],
                empleado_destino['identificacion']
            )
            
            messagebox.showinfo("Éxito", "Tarjetas transferidas correctamente.", parent=self)
            self.callback_actualizar()
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron transferir las tarjetas:\n{e}", parent=self)

    def eliminar_forzado(self):
        """Elimina el empleado y todas sus tarjetas."""
        if not self.var_confirmar_eliminacion.get():
            messagebox.showwarning("Confirmación Requerida", 
                                 "Debe confirmar que entiende las consecuencias.", parent=self)
            return
        
        # Confirmación final
        if not messagebox.askyesno("Confirmación Final", 
                                  f"¿ESTÁ ABSOLUTAMENTE SEGURO de eliminar a "
                                  f"{self.empleado_data['nombre_completo']} y TODAS sus tarjetas?\n\n"
                                  f"Esta acción NO se puede deshacer.", parent=self):
            return
        
        try:
            # Realizar eliminación forzada
            self.api_client.eliminar_empleado_forzado(
                self.empleado_data['identificacion']
            )
            
            messagebox.showinfo("Éxito", "Empleado y tarjetas eliminados correctamente.", parent=self)
            self.callback_actualizar()
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar el empleado:\n{e}", parent=self)

    def eliminar_empleado_simple(self):
        """Elimina el empleado sin tarjetas."""
        if not messagebox.askyesno("Confirmar Eliminación", 
                                  f"¿Está seguro de eliminar a {self.empleado_data['nombre_completo']}?", 
                                  parent=self):
            return
        
        try:
            self.api_client.delete_empleado(self.empleado_data['identificacion'])
            messagebox.showinfo("Éxito", "Empleado eliminado correctamente.", parent=self)
            self.callback_actualizar()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar el empleado:\n{e}", parent=self)

# --- Ventana Emergente para Gestionar Empleados ---
class VentanaGestionEmpleado(tk.Toplevel):
    """Ventana para crear o actualizar un empleado."""
    def __init__(self, parent, callback_actualizar, api_client, empleado_data=None):
        super().__init__(parent)
        self.callback_actualizar = callback_actualizar
        self.api_client = api_client
        self.empleado_data = empleado_data

        self.title("Actualizar Empleado" if empleado_data else "Registrar Empleado")
        self.geometry("420x320")
        self.resizable(False, False)
        self.grab_set() # Hacer la ventana modal

        self.setup_styles()
        self.setup_ui()

        if self.empleado_data:
            self.prellenar_campos()

    def setup_styles(self):
        style = ttk.Style(self)
        style.configure('TLabel', font=('Arial', 10))
        style.configure('TEntry', font=('Arial', 10))
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))

    def setup_ui(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill='both', expand=True)

        title_text = "📝 Actualizar Datos del Empleado" if self.empleado_data else "📝 Registrar Nuevo Empleado"
        ttk.Label(main_frame, text=title_text, style='Header.TLabel').pack(pady=(0, 15))

        self.entry_id = self.create_field(main_frame, "🆔 Identificación:", "id_entry")
        self.entry_nombre = self.create_field(main_frame, "👤 Nombre Completo:", "nombre_entry")
        self.entry_telefono = self.create_field(main_frame, "📞 Teléfono:", "telefono_entry")
        self.entry_direccion = self.create_field(main_frame, "🏠 Dirección:", "direccion_entry")

        ttk.Button(main_frame, text="✅ Guardar", style='Action.TButton', command=self.guardar).pack(pady=(15, 5), fill='x')
        ttk.Button(main_frame, text="✖ Cancelar", command=self.destroy).pack(pady=(0, 10), fill='x')

    def create_field(self, parent, label_text, entry_var_name):
        field_frame = ttk.Frame(parent)
        field_frame.pack(fill='x', pady=5)
        ttk.Label(field_frame, text=label_text, width=15).pack(side='left')
        entry = ttk.Entry(field_frame)
        entry.pack(side='right', fill='x', expand=True)
        setattr(self, entry_var_name, entry)
        return entry

    def prellenar_campos(self):
        self.entry_id.insert(0, self.empleado_data.get('identificacion', ''))
        self.entry_id.config(state='readonly')
        self.entry_nombre.insert(0, self.empleado_data.get('nombre_completo', ''))
        self.entry_telefono.insert(0, self.empleado_data.get('telefono', ''))
        self.entry_direccion.insert(0, self.empleado_data.get('direccion', ''))
        
    def guardar(self):
        identificacion = self.entry_id.get().strip()
        nombre_completo = self.entry_nombre.get().strip()

        if not identificacion or not nombre_completo:
            messagebox.showwarning("Campos Requeridos", "La identificación y el nombre completo son obligatorios.", parent=self)
            return

        empleado_payload = {
            "identificacion": identificacion,
            "nombre_completo": nombre_completo,
            "telefono": self.entry_telefono.get().strip(),
            "direccion": self.entry_direccion.get().strip()
        }

        try:
            if self.empleado_data: # Actualizar
                response = self.api_client.update_empleado(self.empleado_data['identificacion'], empleado_payload)
                success_message = "Empleado actualizado correctamente."
            else: # Crear
                response = self.api_client.create_empleado(empleado_payload)
                success_message = "Empleado registrado correctamente."
            
            messagebox.showinfo("Éxito", success_message, parent=self)
            self.callback_actualizar()
            self.destroy()
            
        except APIError as e:
            messagebox.showerror("Error de API", f"No se pudo guardar el empleado:\n{e.message}", parent=self)
        except Exception as e:
            messagebox.showerror("Error Inesperado", f"Ocurrió un error al guardar:\n{e}", parent=self)

# --- Frame Principal que Contiene Todo ---
class FrameEmpleado(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.empleado_seleccionado = None
        # Usar el cliente global para conservar el token de sesión
        self.api_client = api_client
        self.base_actual = None
        
        self.setup_styles()
        self.setup_ui()
        self.cargar_empleados()

    def setup_styles(self):
        style = ttk.Style()
        style.configure('Main.TLabelframe', font=('Arial', 11, 'bold'))
        style.configure('Main.TLabelframe.Label', font=('Arial', 11, 'bold'))

        # Estilo azul claro reutilizable para botones
        light_blue = '#e6f2ff'
        light_blue_hover = '#d6eaff'
        style.configure('Blue.TButton', font=('Arial', 10, 'bold'), padding=(12, 8), background=light_blue)
        style.map('Blue.TButton', background=[('active', light_blue_hover), ('pressed', light_blue_hover)])

        # Mantener estilos existentes pero con el mismo color base
        style.configure('Action.TButton', font=('Arial', 9, 'bold'), padding=(10, 6), background=light_blue)
        style.configure('Primary.TButton', font=('Arial', 10, 'bold'), padding=(12, 8), background=light_blue)
        style.configure('Secondary.TButton', font=('Arial', 10, 'bold'), padding=(12, 8), background=light_blue)
        style.configure('Info.TButton', font=('Arial', 10), padding=(12, 8), background=light_blue)
        style.map('Action.TButton', background=[('active', light_blue_hover)])
        style.map('Primary.TButton', background=[('active', light_blue_hover)])
        style.map('Secondary.TButton', background=[('active', light_blue_hover)])
        style.map('Info.TButton', background=[('active', light_blue_hover)])
        style.configure('Danger.TButton', font=('Arial', 10, 'bold'), padding=(12, 8))

    def setup_ui(self):
        # Frame principal dividido en tres secciones
        self.frame_izquierdo = ttk.LabelFrame(self, text="👥 Empleados", style='Main.TLabelframe')
        self.frame_izquierdo.pack(side='left', fill='y', padx=5, pady=5)
        # Hacerla más angosta
        self.frame_izquierdo.configure(width=280)
        self.frame_izquierdo.pack_propagate(False)

        self.frame_central = ttk.LabelFrame(self, text="👤 Perfil", style='Main.TLabelframe')
        self.frame_central.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        self.frame_derecho = ttk.LabelFrame(self, text="💰 Base del Día", style='Main.TLabelframe')
        self.frame_derecho.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        self.setup_seccion_empleados()
        self.setup_seccion_perfil()
        self.setup_seccion_base()

    # --- Sección de Lista de Empleados (Izquierda) ---
    def setup_seccion_empleados(self):
        # Lista de empleados
        frame_lista = ttk.Frame(self.frame_izquierdo)
        frame_lista.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.lista_empleados = tk.Listbox(frame_lista, font=('Arial', 10), selectbackground='#0078d4', selectforeground='white')
        scrollbar = ttk.Scrollbar(frame_lista, orient="vertical", command=self.lista_empleados.yview)
        self.lista_empleados.config(yscrollcommand=scrollbar.set)
        
        self.lista_empleados.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.lista_empleados.bind('<<ListboxSelect>>', self.on_empleado_seleccionado)

        # Botones de gestión se movieron a la sección de Perfil

    # --- Sección de Perfil de Empleado (Central) ---
    def setup_seccion_perfil(self):
        main_frame = ttk.Frame(self.frame_central)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.perfil_fields = {}
        self.perfil_fields['identificacion'] = self.create_profile_field(main_frame, "🆔", "Identificación")
        self.perfil_fields['nombre_completo'] = self.create_profile_field(main_frame, "👤", "Nombre Completo")
        self.perfil_fields['telefono'] = self.create_profile_field(main_frame, "📞", "Teléfono")
        self.perfil_fields['direccion'] = self.create_profile_field(main_frame, "🏠", "Dirección")
        # Eliminado IMEI según requerimiento

        # Barra de acciones (AGREGAR, EDITAR, ELIMINAR, ASIGNAR IMEI)
        acciones = ttk.Frame(main_frame)
        acciones.pack(fill='x', pady=12)
        acciones.columnconfigure(0, weight=1)
        acciones.columnconfigure(1, weight=1)
        acciones.columnconfigure(2, weight=1)
        acciones.columnconfigure(3, weight=1)
        ttk.Button(acciones, text="➕ Agregar", style='Blue.TButton', command=self.mostrar_ventana_agregar).grid(row=0, column=0, padx=5, sticky='ew')
        ttk.Button(acciones, text="✏️ Editar", style='Blue.TButton', command=self.mostrar_ventana_actualizar).grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Button(acciones, text="🗑️ Eliminar | Transferir", style='Blue.TButton', command=self.eliminar_empleado_seleccionado).grid(row=0, column=2, padx=5, sticky='ew')
        ttk.Button(acciones, text="👤 Usuario cobrador", style='Blue.TButton', command=self.gestionar_usuario_cobrador).grid(row=0, column=3, padx=5, sticky='ew')

    def create_profile_field(self, parent, icon, label_text):
        field_frame = ttk.Frame(parent)
        field_frame.pack(fill='x', pady=5)
        ttk.Label(field_frame, text=f"{icon} {label_text}", font=('Arial', 9, 'bold')).pack(anchor='w')
        entry = ttk.Entry(field_frame, font=('Arial', 10), state='readonly')
        entry.pack(fill='x', pady=(2, 0))
        return entry

    # --- Sección de Base del Día (Derecha) ---
    def setup_seccion_base(self):
        main_frame = ttk.Frame(self.frame_derecho)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Fecha
        ttk.Label(main_frame, text="📅 Fecha:", font=('Arial', 9, 'bold')).pack(anchor='w')
        fecha_input_frame = ttk.Frame(main_frame)
        fecha_input_frame.pack(fill='x', pady=(2, 10))
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        self.entry_fecha = DateEntry(
            fecha_input_frame,
            textvariable=self.date_var,
            date_pattern='yyyy-MM-dd',
            width=18,
            background='darkblue',
            foreground='white',
            borderwidth=2
        )
        self.entry_fecha.pack(side='left', fill='x', expand=True)
        
        # Monto Actual
        ttk.Label(main_frame, text="💰 Monto Actual:", font=('Arial', 9, 'bold')).pack(anchor='w')
        self.label_monto = ttk.Label(main_frame, text="N/A", font=('Arial', 12, 'bold'), foreground='gray')
        self.label_monto.pack(anchor='w', pady=(2, 10))
        
        # Status
        self.status_label = ttk.Label(main_frame, text="Seleccione un empleado y fecha", font=('Arial', 8, 'italic'))
        self.status_label.pack(anchor='w')

        # Botones de gestión de base (AGREGAR, ACTUALIZAR, ELIMINAR, BUSCAR)
        frame_botones = ttk.Frame(main_frame)
        frame_botones.pack(fill='x', pady=15)
        frame_botones.columnconfigure(0, weight=1)
        # Botones en columna vertical más anchos
        ttk.Button(frame_botones, text="➕ Agregar Base", style='Blue.TButton', command=self.agregar_base).grid(row=0, column=0, padx=5, pady=4, sticky='ew')
        ttk.Button(frame_botones, text="✏️ Actualizar Base", style='Blue.TButton', command=self.actualizar_base).grid(row=1, column=0, padx=5, pady=4, sticky='ew')
        ttk.Button(frame_botones, text="🗑️ Eliminar Base", style='Blue.TButton', command=self.eliminar_base).grid(row=2, column=0, padx=5, pady=4, sticky='ew')
        ttk.Button(frame_botones, text="🔎 Buscar Base", style='Blue.TButton', command=self.buscar_base).grid(row=3, column=0, padx=5, pady=4, sticky='ew')

    # --- Métodos de Lógica y Eventos ---
    
    def cargar_empleados(self):
        """Carga la lista de empleados desde la API."""
        try:
            empleados = self.api_client.list_empleados()
            self.empleados_cache = sorted(empleados, key=lambda emp: emp['nombre_completo'].lower())
            
            self.lista_empleados.delete(0, tk.END)
            self.empleados_dict = {emp['nombre_completo']: emp for emp in self.empleados_cache}
            
            for emp in self.empleados_cache:
                self.lista_empleados.insert(tk.END, emp['nombre_completo'])
            self.limpiar_todo()
        except Exception as e:
            messagebox.showerror("Error de Carga", f"No se pudo cargar la lista de empleados:\n{e}")

    def on_empleado_seleccionado(self, event=None):
        """Maneja la selección de un empleado en la Listbox."""
        seleccion = self.lista_empleados.curselection()
        if not seleccion:
            return
            
        nombre_seleccionado = self.lista_empleados.get(seleccion[0])
        self.empleado_seleccionado = self.empleados_dict.get(nombre_seleccionado)
        
        if self.empleado_seleccionado:
            self.actualizar_campos_perfil()
            self.buscar_base()

    def actualizar_campos_perfil(self):
        """Actualiza los campos de la sección de perfil."""
        if not self.empleado_seleccionado:
            self.limpiar_campos_perfil()
            return

        for key, entry in self.perfil_fields.items():
            entry.config(state='normal')
            entry.delete(0, tk.END)
            entry.insert(0, self.empleado_seleccionado.get(key, ''))
            entry.config(state='readonly')
            
    def asignar_imei(self):
        """Abre un dialogo para asignar un IMEI al empleado seleccionado."""
        if not self.empleado_seleccionado:
            messagebox.showwarning("Sin Selección", "Por favor, seleccione un empleado.")
            return

        imei_actual = self.empleado_seleccionado.get('imei', '')
        nuevo_imei = simpledialog.askstring("Asignar IMEI", 
                                            f"Ingrese el IMEI para {self.empleado_seleccionado['nombre_completo']}:",
                                            initialvalue=imei_actual, parent=self)

        if nuevo_imei is not None: # Si el usuario no presiona "Cancelar"
            try:
                payload = {"imei": nuevo_imei.strip()}
                self.api_client.update_empleado(self.empleado_seleccionado['identificacion'], payload)
                messagebox.showinfo("Éxito", "IMEI actualizado correctamente.")
                # Actualizar cache local y UI
                self.empleado_seleccionado['imei'] = nuevo_imei.strip()
                self.actualizar_campos_perfil()
            except Exception as e:
                messagebox.showerror("Error de API", f"No se pudo actualizar el IMEI:\n{e}")

    def gestionar_usuario_cobrador(self):
        if not self.empleado_seleccionado:
            messagebox.showwarning("Sin Selección", "Seleccione un empleado para gestionar su usuario cobrador.")
            return
        VentanaUsuarioCobrador(self, self.api_client, self.empleado_seleccionado)

    # --- Métodos para Gestión de Base ---
    def buscar_base(self):
        """Busca una base para el empleado y fecha actuales."""
        if not self.empleado_seleccionado:
            self.actualizar_status_base("Seleccione un empleado", "orange")
            return

        fecha_str = self.entry_fecha.get()
        if not fecha_str:
            self.actualizar_status_base("Ingrese una fecha", "orange")
            return
            
        try:
            base = self.api_client.get_base_by_empleado_fecha(self.empleado_seleccionado['identificacion'], fecha_str)
            # Si la API devuelve None (no hay base), actualizar UI sin mostrar popups
            if not base:
                self.base_actual = None
                self.label_monto.config(text="No registrada", foreground='gray')
                self.actualizar_status_base("No hay base para esta fecha.", "red")
                return
            # Hay base
            self.base_actual = base
            monto = Decimal(self.base_actual.get('monto', 0))
            self.label_monto.config(text=f"${monto:,.0f}", foreground='green')
            self.actualizar_status_base("Base encontrada.", "green")
        except APIError as e:
            if e.status_code == 404:
                self.base_actual = None
                self.label_monto.config(text="No registrada", foreground='gray')
                self.actualizar_status_base("No hay base para esta fecha.", "red")
            else:
                self.actualizar_status_base("Error al buscar la base.", "red")
        except Exception:
            # Evitar ventanas emergentes aquí; solo actualizar estado
            self.actualizar_status_base("Error al consultar base.", "red")

    def agregar_base(self):
        if not self.empleado_seleccionado:
            messagebox.showwarning("Sin Selección", "Seleccione un empleado para agregarle una base.")
            return
        if self.base_actual:
            messagebox.showwarning("Base Existente", "Ya existe una base para esta fecha. Use 'Actualizar' en su lugar.")
            return

        monto_str = simpledialog.askstring("Agregar Base", "Ingrese el monto de la nueva base:", parent=self)
        if monto_str:
            try:
                monto = Decimal(monto_str)
                payload = {
                    "empleado_id": self.empleado_seleccionado['identificacion'],
                    "fecha": self.entry_fecha.get(),
                    "monto": float(monto)
                }
                self.api_client.create_base(payload)
                messagebox.showinfo("Éxito", "Base agregada correctamente.")
                self.buscar_base() # Refrescar la info
            except ValueError:
                messagebox.showerror("Error de Formato", "El monto ingresado no es un número válido.")
            except Exception as e:
                messagebox.showerror("Error de API", f"No se pudo agregar la base:\n{e}")

    def actualizar_base(self):
        if not self.base_actual:
            messagebox.showwarning("Sin Base", "Primero busque una base existente para poder actualizarla.")
            return

        monto_actual = str(self.base_actual.get('monto', '0'))
        nuevo_monto_str = simpledialog.askstring("Actualizar Base", "Ingrese el nuevo monto:", initialvalue=monto_actual, parent=self)
        
        if nuevo_monto_str:
            try:
                nuevo_monto = Decimal(nuevo_monto_str)
                payload = {"monto": float(nuevo_monto)}
                self.api_client.update_base(self.base_actual['id'], payload)
                messagebox.showinfo("Éxito", "Base actualizada correctamente.")
                self.buscar_base() # Refrescar la info
            except ValueError:
                messagebox.showerror("Error de Formato", "El monto ingresado no es un número válido.")
            except Exception as e:
                messagebox.showerror("Error de API", f"No se pudo actualizar la base:\n{e}")

    def eliminar_base(self):
        if not self.base_actual:
            messagebox.showwarning("Sin Base", "Primero busque una base existente para poder eliminarla.")
            return
            
        if messagebox.askyesno("Confirmar Eliminación", "¿Está seguro de que desea eliminar la base seleccionada?"):
            try:
                self.api_client.delete_base(self.base_actual['id'])
                messagebox.showinfo("Éxito", "Base eliminada correctamente.")
                self.buscar_base() # Refrescar la info
            except Exception as e:
                messagebox.showerror("Error de API", f"No se pudo eliminar la base:\n{e}")

    # --- Métodos de UI y Helpers ---
    def mostrar_ventana_agregar(self):
        VentanaGestionEmpleado(self, self.cargar_empleados, self.api_client)
        
    def mostrar_ventana_actualizar(self):
        if self.empleado_seleccionado:
            VentanaGestionEmpleado(self, self.cargar_empleados, self.api_client, self.empleado_seleccionado)
        else:
            messagebox.showwarning("Sin Selección", "Por favor, seleccione un empleado de la lista para editar.")

    def eliminar_empleado_seleccionado(self):
        if not self.empleado_seleccionado:
            messagebox.showwarning("Sin Selección", "Por favor, seleccione un empleado de la lista para eliminar.")
            return
            
        # Abrir la ventana de eliminación con opciones
        VentanaEliminarEmpleado(self, self.cargar_empleados, self.api_client, self.empleado_seleccionado)
    
    def mostrar_calendario(self):
        try:
            # Abrir el desplegable del DateEntry para seleccionar fecha
            self.entry_fecha.event_generate('<Button-1>')
        except Exception:
            pass

    def actualizar_status_base(self, mensaje, color):
        self.status_label.config(text=mensaje, foreground=color)

    def limpiar_campos_perfil(self):
        for entry in self.perfil_fields.values():
            entry.config(state='normal')
            entry.delete(0, tk.END)
            entry.config(state='readonly')

    def limpiar_todo(self):
        self.empleado_seleccionado = None
        self.base_actual = None
        self.limpiar_campos_perfil()
        self.label_monto.config(text="N/A", foreground='gray')
        self.actualizar_status_base("Seleccione un empleado", "black")


class VentanaUsuarioCobrador(tk.Toplevel):
    def __init__(self, parent, api_client, empleado_data):
        super().__init__(parent)
        self.parent = parent
        self.api_client = api_client
        self.empleado = empleado_data
        self.title("Usuario Cobrador")
        self.geometry("480x620")
        self.resizable(False, False)
        self.grab_set()
        try:
            self.center_window()
        except Exception:
            pass

        # Estado interno
        self.estado_activo = None
        self.credenciales_existen = False

        self.setup_ui()
        self.cargar_estado_inicial()

    def setup_ui(self):
        # Estilos modernos
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Card.TFrame', background="#F8FAFC")
        style.configure('Header.TLabel', font=('Segoe UI', 13, 'bold'))
        style.configure('TLabel', font=('Segoe UI', 11))
        style.configure('Subtle.TLabel', foreground='#6B7280', font=('Segoe UI', 10))
        style.configure('Primary.TButton', font=('Segoe UI', 11, 'bold'), foreground='white', background='#4F46E5')
        style.map('Primary.TButton', background=[('active', '#4338CA'), ('pressed', '#4338CA')])
        # Secciones con fondo suave y acento índigo
        style.configure('Section.TLabelframe', background='#EEF2FF')
        style.configure('Section.TLabelframe.Label', background='#EEF2FF', foreground='#3730A3', font=('Segoe UI', 11, 'bold'))
        style.configure('Section.TFrame', background='#EEF2FF')

        cont = ttk.Frame(self, padding=16, style='Card.TFrame')
        cont.pack(fill='both', expand=True)

        # Encabezado con estado
        header = ttk.Frame(cont, style='Card.TFrame')
        header.pack(fill='x')
        ttk.Label(header, text=f"Empleado: {self.empleado.get('nombre_completo','')}", style='Header.TLabel').pack(anchor='w')
        self.lbl_estado = ttk.Label(header, text="Estado: --", style='Subtle.TLabel')
        self.lbl_estado.pack(anchor='w', pady=(2,8))

        # Credenciales
        cred = ttk.LabelFrame(cont, text="Credenciales", padding=12, style='Section.TLabelframe')
        cred.pack(fill='x')
        ttk.Label(cred, text="Usuario").grid(row=0, column=0, sticky='w')
        recomendado = (self.empleado.get('nombre_completo','') or '').strip().replace(' ', '.').lower()
        self.entry_user = ttk.Entry(cred, width=32)
        self.entry_user.grid(row=0, column=1, sticky='ew', padx=(8,0))
        if recomendado:
            self.entry_user.insert(0, recomendado)
        ttk.Label(cred, text="Contraseña (>=4)").grid(row=1, column=0, sticky='w', pady=(8,0))
        self.entry_pass = ttk.Entry(cred, width=32)
        self.entry_pass.grid(row=1, column=1, sticky='ew', padx=(8,0), pady=(8,0))
        cred.grid_columnconfigure(1, weight=1)

        # Botón principal: crear/activar/desactivar usuario cobrador (según estado)
        self.btn_crear_toggle = ttk.Button(cont, text="Crear credenciales", style='Primary.TButton', command=self.on_crear_o_toggle)
        self.btn_crear_toggle.pack(fill='x', pady=(8,0))

        preview = ttk.LabelFrame(cont, text="Vista previa del login", padding=12, style='Section.TLabelframe')
        preview.pack(fill='x', pady=(12,0))
        form = ttk.Frame(preview, style='Section.TFrame')
        form.pack(pady=4, fill='x')
        ttk.Label(form, text="Usuario").grid(row=0, column=0, sticky='w')
        self.preview_user_entry = ttk.Entry(form, width=32)
        self.preview_user_entry.grid(row=0, column=1, sticky='ew', padx=(8,0))
        ttk.Label(form, text="Contraseña").grid(row=1, column=0, sticky='w', pady=(6,0))
        self.preview_pass_entry = ttk.Entry(form, width=32)
        self.preview_pass_entry.grid(row=1, column=1, sticky='ew', padx=(8,0), pady=(6,0))
        form.grid_columnconfigure(1, weight=1)
        # Botón para actualizar credenciales (debajo del preview)
        self.btn_actualizar = ttk.Button(cont, text="Actualizar credenciales", style='Primary.TButton', command=self.on_actualizar)
        self.btn_actualizar.pack(fill='x', pady=(10,0))

        def actualizar_preview(*args):
            self.preview_user_entry.delete(0, tk.END)
            self.preview_user_entry.insert(0, self.entry_user.get().strip())
            self.preview_pass_entry.delete(0, tk.END)
            self.preview_pass_entry.insert(0, self.entry_pass.get().strip())
        self.entry_user.bind('<KeyRelease>', actualizar_preview)
        self.entry_pass.bind('<KeyRelease>', actualizar_preview)

        # Permisos de hoy (lado a lado, estilo robusto)
        perms = ttk.LabelFrame(cont, text="Permisos de hoy (app móvil)", padding=12, style='Section.TLabelframe')
        perms.pack(fill='x', pady=(12,0))
        self.lbl_fecha_perm = ttk.Label(perms, text="Fecha acción: --", style='Subtle.TLabel')
        self.lbl_fecha_perm.pack(anchor='w')

        fila = ttk.Frame(perms, style='Section.TFrame')
        fila.pack(fill='x', pady=(8,0))
        self.lbl_descargar = tk.Label(fila, text="📱⬇️ Descargar", cursor='hand2', font=('Segoe UI', 11, 'bold'),
                                      bg='#E5E7EB', padx=16, pady=12, relief='raised')
        self.lbl_descargar.pack(side='left', padx=(0,8), fill='x', expand=True)
        # Habilitar permisos en conjunto: al habilitar uno, habilitar ambos
        self.lbl_descargar.bind('<Button-1>', lambda e: self._rehabilitar_permiso(descargar=True, subir=True))

        self.lbl_subir = tk.Label(fila, text="📱⬆️ Subir", cursor='hand2', font=('Segoe UI', 11, 'bold'),
                                   bg='#E5E7EB', padx=16, pady=12, relief='raised')
        self.lbl_subir.pack(side='left', fill='x', expand=True)
        self.lbl_subir.bind('<Button-1>', lambda e: self._rehabilitar_permiso(descargar=True, subir=True))

        ttk.Label(perms, text="Azul = permitido, Rojo = ya usado hoy. Click para re-habilitar.",
                  foreground='#2563EB').pack(anchor='w', pady=(6,0))

        # Botones de acción
        btns = ttk.Frame(cont, style='Card.TFrame')
        btns.pack(fill='x', pady=12)
        ttk.Button(btns, text="Cerrar", command=self.destroy).pack(side='right')

    def cargar_estado_inicial(self):
        # Cargar credenciales y estado activo/inactivo
        try:
            creds = self.api_client.get_cobrador_credentials(self.empleado['identificacion'])
            
            # Manejar caso donde creds es None o no es un diccionario
            if not creds or not isinstance(creds, dict):
                self.credenciales_existen = False
                username = ''
                password = ''
                self.estado_activo = None
            else:
                # Verificar si existen credenciales (activo o inactivo)
                self.credenciales_existen = bool(creds.get('exists')) or bool(creds.get('username'))
                username = creds.get('username') or ''
                password = creds.get('password') or ''
                
                # Obtener estado (puede ser True, False o None)
                self.estado_activo = creds.get('is_active') if creds and 'is_active' in creds else None
            
            # Cargar credenciales en los campos (siempre que existan)
            if username:
                self.entry_user.delete(0, tk.END)
                self.entry_user.insert(0, username)
            if password:
                # Cargar password real si está disponible
                self.entry_pass.delete(0, tk.END)
                self.entry_pass.insert(0, password)
                
            # Sincronizar preview
            for _ in range(2):
                self.entry_user.event_generate('<KeyRelease>')
                self.entry_pass.event_generate('<KeyRelease>')
        except Exception as e:
            print(f"DEBUG: Error al cargar credenciales: {e}")  # Debug temporal
            self.credenciales_existen = False
            self.estado_activo = None

        # Actualizar etiquetas de estado
        self._actualizar_estado_ui()
        # Leer permisos usando la nueva lógica simple
        try:
            estado = self.api_client.get_permisos_empleado(self.empleado['identificacion'])
            fa = estado.get('fecha_accion') or '--'
            self.lbl_fecha_perm.config(text=f"Fecha acción: {fa}")
            
            # Usar los valores calculados directamente del backend
            descargar_ok = bool(estado.get('puede_descargar', False))
            subir_ok = bool(estado.get('puede_subir', False))
            
            self._pintar_permiso(self.lbl_descargar, descargar_ok)
            self._pintar_permiso(self.lbl_subir, subir_ok)
        except Exception as e:
            print(f"Error al cargar permisos: {e}")
            # En caso de error, mostrar como no disponibles
            self._pintar_permiso(self.lbl_descargar, False)
            self._pintar_permiso(self.lbl_subir, False)

    def on_actualizar(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()
        if not username or not password or len(password) < 4:
            messagebox.showwarning("Campos requeridos", "Ingrese usuario y contraseña (mín. 4).")
            return
        try:
            self.api_client.upsert_cobrador_credentials(self.empleado['identificacion'], username, password)
            self.credenciales_existen = True
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar credenciales: {e}")
            return
        messagebox.showinfo("Hecho", "Credenciales actualizadas.")
        # Mantener credenciales en entries y reflejar en preview
        try:
            self.preview_user_entry.delete(0, tk.END)
            self.preview_user_entry.insert(0, username)
            self.preview_pass_entry.delete(0, tk.END)
            self.preview_pass_entry.insert(0, password)
        except Exception:
            pass
        self._actualizar_estado_ui()

    def on_crear_o_toggle(self):
        """Crea y activa el usuario cobrador si no existe; si existe, alterna activar/desactivar según estado.
        Respeta el cupo del plan: si la API retorna 409 por límite, mostrar mensaje y sugerir desactivar otro.
        """
        emp_id = self.empleado['identificacion']
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()
        # Si no hay credenciales creadas, crear y activar
        if not self.credenciales_existen:
            if not username or not password or len(password) < 4:
                messagebox.showwarning("Campos requeridos", "Ingrese usuario y contraseña (mín. 4).")
                return
            try:
                # Crea credenciales (ya queda ACTIVO por defecto en el backend)
                self.api_client.create_cobrador(username=username, password=password, empleado_identificacion=emp_id)
                messagebox.showinfo("Hecho", "Usuario cobrador creado y activado.")
                # Mantener credenciales en entries y preview
                self.preview_user_entry.delete(0, tk.END)
                self.preview_user_entry.insert(0, username)
                self.preview_pass_entry.delete(0, tk.END)
                self.preview_pass_entry.insert(0, password)
                # Refrescar datos desde la API para poblar entries y permisos
                self.cargar_estado_inicial()
            except APIError as e:
                if e.status_code in (403, 409):
                    messagebox.showerror("Sin cupo disponible", "No hay cupos de usuario cobrador disponibles en su plan. Desactive alguno para liberar cupo.")
                else:
                    messagebox.showerror("Error", f"No se pudo crear el usuario cobrador: {e.message}")
                return
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo crear el usuario cobrador: {e}")
                return
        else:
            # Si existe, alternar estado respetando cupos del plan
            try:
                if self.estado_activo:
                    self.api_client.deactivate_cobrador(emp_id)
                    self.estado_activo = False
                    messagebox.showinfo("Hecho", "Usuario cobrador desactivado. Cupo liberado.")
                else:
                    self.api_client.activate_cobrador(emp_id)
                    self.estado_activo = True
                    messagebox.showinfo("Hecho", "Usuario cobrador activado.")
            except APIError as e:
                if e.status_code in (403, 409):
                    messagebox.showerror("Sin cupo disponible", "No hay cupos disponibles para activar otro usuario cobrador. Desactive alguno en otra ruta.")
                else:
                    messagebox.showerror("Error", f"No se pudo cambiar estado: {e.message}")
                return
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cambiar estado: {e}")
                return
        # Refrescar UI
        self._actualizar_estado_ui()

    def on_toggle_estado(self):
        try:
            emp_id = self.empleado['identificacion']
            if self.estado_activo:
                self.api_client.deactivate_cobrador(emp_id)
                self.estado_activo = False
            else:
                self.api_client.activate_cobrador(emp_id)
                self.estado_activo = True
            self._actualizar_estado_ui()
        except APIError as e:
            messagebox.showerror("Error", f"No se pudo cambiar el estado: {e.message}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cambiar el estado: {e}")

    def _pintar_permiso(self, label_widget, permitido: bool):
        # Azul si permitido, rojo si ya usado hoy
        label_widget.configure(fg=("#2563EB" if permitido else "#DC2626"),
                               bg=("#E5F0FF" if permitido else "#FEE2E2"))

    def _rehabilitar_permiso(self, descargar: bool = False, subir: bool = False):
        """Re-habilitar permisos. Regla: si se habilita uno, se habilitan ambos."""
        try:
            # Usar el nuevo endpoint de rehabilitar permisos
            # Forzar habilitación conjunta según decisión funcional
            estado = self.api_client.rehabilitar_permisos(
                self.empleado['identificacion'], 
                descargar=True if (descargar or subir) else False, 
                subir=True if (descargar or subir) else False
            )
            
            # Actualizar UI con los valores calculados del backend
            fa = estado.get('fecha_accion') or '--'
            self.lbl_fecha_perm.config(text=f"Fecha acción: {fa}")
            
            # Usar los valores calculados directamente del backend
            descargar_ok = bool(estado.get('puede_descargar', False))
            subir_ok = bool(estado.get('puede_subir', False))
            
            self._pintar_permiso(self.lbl_descargar, descargar_ok)
            self._pintar_permiso(self.lbl_subir, subir_ok)
            
            # Mostrar mensaje de confirmación
            mensaje = "Permisos re-habilitados: descargar y subir"
            messagebox.showinfo("Permisos actualizados", mensaje)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo re-habilitar permiso: {e}")

    def _actualizar_estado_ui(self):
        try:
            # Determinar texto y color del estado
            if self.estado_activo is True:
                estado_txt = "Activo"
                color = '#059669'  # Verde
            elif self.estado_activo is False:
                estado_txt = "Inactivo"
                color = '#DC2626'  # Rojo
            else:
                estado_txt = "Desconocido"
                color = '#6B7280'  # Gris
            
            self.lbl_estado.config(text=f"Estado: {estado_txt}", foreground=color)
            
            # Botón principal crear/toggle
            if not self.credenciales_existen:
                self.btn_crear_toggle.config(text="Crear credenciales")
            else:
                if self.estado_activo is True:
                    self.btn_crear_toggle.config(text="Desactivar usuario cobrador")
                elif self.estado_activo is False:
                    self.btn_crear_toggle.config(text="Activar usuario cobrador")
                else:
                    self.btn_crear_toggle.config(text="Estado desconocido")
            
            # Botón actualizar credenciales visible siempre
            self.btn_actualizar.config(text="Actualizar credenciales")
        except Exception as e:
            pass

    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")


