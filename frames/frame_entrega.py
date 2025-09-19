import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from decimal import Decimal
import logging
from tkinter import Toplevel

# Importar el cliente de la API desde la nueva ruta raíz
from api_client.client import api_client

logger = logging.getLogger(__name__)

class FrameEntrega(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        # Usar cliente global con token de sesión
        self.api_client = api_client
        self.empleados_dict = {}
        # Caché de abonos por código de tarjeta
        self._abonos_cache_por_tarjeta = {}
        self._abonos_prefetch_thread = None
        self._empleado_en_prefetch = None
        
        style = ttk.Style()
        style.configure('Contraste.TFrame', background='#E0E0E0')
        self.setup_ui()
        self.cargar_empleados()

    def setup_ui(self):
        # Frame principal dividido en tres secciones con anchos específicos
        self.frame_izquierdo = ttk.LabelFrame(self, text="Cobro", width=450)  # Aumentado 1cm
        self.frame_izquierdo.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        self.frame_izquierdo.pack_propagate(False)

        self.frame_central = ttk.LabelFrame(self, text="Ver", width=180)
        self.frame_central.pack(side='left', fill='y', padx=5, pady=5)
        self.frame_central.pack_propagate(False)

        self.frame_derecho = ttk.LabelFrame(self, text="Abonos", width=450)  # Reducido 1cm
        self.frame_derecho.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        self.frame_derecho.pack_propagate(False)

        self.setup_seccion_cobro()
        self.setup_seccion_ver()
        self.setup_seccion_abonos()

    def setup_seccion_cobro(self):
        # Frame para los controles de selección
        frame_seleccion = ttk.Frame(self.frame_izquierdo)
        frame_seleccion.pack(fill='x', padx=5, pady=5)

        # Fila única para selección de empleado y estado
        ttk.Label(frame_seleccion, text="Seleccione un empleado").pack(side='left', padx=(0,5))
        self.combo_empleados = ttk.Combobox(frame_seleccion, width=25, state="readonly")
        self.combo_empleados.pack(side='left', padx=5)
        # Al abrir el combo, recargar empleados desde la API para reflejar altas recientes
        self.combo_empleados.bind('<Button-1>', lambda e: self.cargar_empleados())
        # Botón de refresco manual
        ttk.Button(frame_seleccion, text="↻", width=3, command=self.cargar_empleados).pack(side='left', padx=(0,5))
        
        self.combo_estado = ttk.Combobox(frame_seleccion, width=12, 
                                       values=['activas', 'cancelada', 'pendiente'],
                                       state="readonly")
        self.combo_estado.pack(side='left', padx=5)
        self.combo_estado.set('activas')

        # Frame para etiquetas de tarjetas
        frame_tarjetas = ttk.Frame(self.frame_izquierdo)
        frame_tarjetas.pack(fill='x', padx=5)
        ttk.Label(frame_tarjetas, text="Tarjetas").pack(side='left')
        ttk.Label(frame_tarjetas, text="###").pack(side='left', padx=5)
        
        # Frame para la tabla con fondo contrastante más oscuro
        self.frame_tabla = tk.Frame(self.frame_izquierdo, bg='#E0E0E0')
        self.frame_tabla.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Configurar la tabla con las columnas en el orden correcto
        columns = ('ruta', 'monto', 'nombre', 'apellido', 'fecha', 'cuotas')
        self.tree = ttk.Treeview(self.frame_tabla, columns=columns, show='headings', height=15)
        
        # Configurar el estilo base del Treeview
        style = ttk.Style()
        
        # Configurar el estilo general
        style.configure('Treeview', 
                       background='white',
                       foreground='black',
                       rowheight=25,
                       fieldbackground='white')
        
        # SOLUCIÓN RADICAL: En vez de usar background, usamos foreground para distinguir tarjetas nuevas
        # Las tarjetas nuevas tendrán texto en verde oscuro, evitando conflicto con la selección
        self.tree.tag_configure('nueva', foreground='#006400')  # Verde oscuro para el texto
        
        # Configurar columnas con sus nombres y anchos específicos
        anchos = {
            'ruta': 70,
            'monto': 100,
            'nombre': 150,
            'apellido': 150,
            'fecha': 100,
            'cuotas': 70
        }
        
        # Configurar encabezados con nombres más descriptivos
        headers = {
            'ruta': 'Ruta',
            'monto': 'Monto Total',
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'fecha': 'Fecha Créd.',
            'cuotas': 'Cuotas'
        }
        
        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=anchos[col])

        # Crear y configurar scrollbars
        self.scrollbar_y = ttk.Scrollbar(self.frame_tabla, orient="vertical", command=self.tree.yview)
        self.scrollbar_x = ttk.Scrollbar(self.frame_tabla, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)

        # Posicionar tabla y scrollbars usando grid
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.scrollbar_x.grid(row=1, column=0, sticky="ew")

        # Configurar el frame_tabla para expandirse
        self.frame_tabla.grid_rowconfigure(0, weight=1)
        self.frame_tabla.grid_columnconfigure(0, weight=1)

        # Eventos
        self.combo_empleados.bind('<<ComboboxSelected>>', self.on_seleccion_cambio)
        self.combo_estado.bind('<<ComboboxSelected>>', self.on_seleccion_cambio)

    def cargar_empleados(self):
        """Carga los empleados desde la API."""
        try:
            self.combo_empleados.set('')
            empleados = self.api_client.list_empleados()
            
            if empleados:
                # El diccionario ahora mapea nombre_completo -> identificacion
                self.empleados_dict = {emp['nombre_completo']: emp['identificacion'] for emp in empleados}
                
                nombres = list(self.empleados_dict.keys())
                self.combo_empleados['values'] = nombres
                if nombres:
                    self.combo_empleados.set(nombres[0])
                    # Llamar a mostrar_tabla_tarjetas solo después de seleccionar un empleado
                self.mostrar_tabla_tarjetas()
        except Exception as e:
            logger.error(f"Error al cargar empleados desde la API: {e}")
            messagebox.showerror("Error de API", f"No se pudieron cargar los empleados: {e}")

    def on_seleccion_cambio(self, event=None):
        """Maneja el cambio de selección de empleado o estado"""
        if self.combo_empleados.get() and self.combo_estado.get():
            self.mostrar_tabla_tarjetas()

    def mostrar_tabla_tarjetas(self, nueva_tarjeta_id=None):
        """Muestra las tarjetas en la tabla obteniéndolas desde la API."""
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            empleado_nombre = self.combo_empleados.get()
            if not empleado_nombre:
                return
            
            empleado_id = self.empleados_dict.get(empleado_nombre)
            if not empleado_id:
                return
            
            estado = self.combo_estado.get()
            tarjetas = self.api_client.list_tarjetas(empleado_id=empleado_id, estado=estado, limit=200)
            
            fecha_actual = datetime.now().date()
            
            # Limpiar caché cuando cambia empleado/estado y preparar prefetch
            self._abonos_cache_por_tarjeta = {}
            codigos_para_prefetch = []

            for tarjeta in tarjetas:
                fecha_creacion_dt = datetime.fromisoformat(tarjeta['fecha_creacion'].replace('Z', '+00:00'))
                fecha_tarjeta = fecha_creacion_dt.date()
                es_nueva = fecha_tarjeta == fecha_actual
                
                fecha_str = fecha_tarjeta.strftime('%d/%m/%Y')
                
                numero_ruta = tarjeta.get('numero_ruta')
                if numero_ruta is not None:
                    try:
                        ruta_int = int(float(numero_ruta))
                        ruta_str = f"{ruta_int}"
                    except Exception:
                        ruta_str = str(numero_ruta)
                else:
                    ruta_str = "0"
                
                # Compatibilidad: aceptar tanto estructura anidada como campos planos
                cliente_obj = tarjeta.get('cliente') if isinstance(tarjeta.get('cliente'), dict) else None
                nombre_cliente = (
                    (cliente_obj.get('nombre') if cliente_obj and 'nombre' in cliente_obj else tarjeta.get('cliente_nombre', ''))
                ).upper()
                apellido_cliente = (
                    (cliente_obj.get('apellido') if cliente_obj and 'apellido' in cliente_obj else tarjeta.get('cliente_apellido', ''))
                ).upper()

                # El iid del item en el Treeview será el ID/código de la tarjeta
                item_id = self.tree.insert('', 'end', values=(
                    ruta_str,
                    f"${tarjeta['monto']:,.0f}",
                    nombre_cliente,
                    apellido_cliente,
                    fecha_str,
                    tarjeta['cuotas'],
                    tarjeta['codigo']
                ), iid=tarjeta.get('id', tarjeta.get('codigo')))

                # Acumular códigos de tarjeta para prefetch
                try:
                    cod_tar = str(tarjeta.get('codigo') or tarjeta.get('id') or '')
                    if cod_tar:
                        codigos_para_prefetch.append(cod_tar)
                except Exception:
                    pass
                
                if es_nueva:
                    self.tree.item(item_id, tags=('nueva',))
                
                if nueva_tarjeta_id and (tarjeta.get('id', tarjeta.get('codigo')) == nueva_tarjeta_id):
                    self.tree.selection_set(item_id)
                    self.tree.see(item_id)
                    self.tree.focus(item_id)

            # Lanzar prefetch de abonos en segundo plano (no bloquea UI)
            self._lanzar_prefetch_abonos(empleado_id, codigos_para_prefetch)
                
        except Exception as e:
            logger.error(f"Error al mostrar tarjetas desde la API: {e}")
            messagebox.showerror("Error de API", f"Error al mostrar tarjetas: {e}")

    def _lanzar_prefetch_abonos(self, empleado_id: str, codigos: list):
        """Dispara un hilo que precarga abonos para los códigos dados y los guarda en caché."""
        import threading
        try:
            self._empleado_en_prefetch = empleado_id

            def _worker():
                for codigo in codigos:
                    # Si el empleado cambió, detener prefetch
                    if self._empleado_en_prefetch != empleado_id:
                        break
                    if codigo in self._abonos_cache_por_tarjeta:
                        continue
                    try:
                        abonos = self.api_client.list_abonos_by_tarjeta(codigo)
                        abonos = self._sort_abonos_asc(abonos)
                        rows = self._build_abono_rows(abonos, codigo)
                        self._abonos_cache_por_tarjeta[codigo] = rows
                        # Si esta tarjeta está seleccionada actualmente, actualizar UI con caché
                        try:
                            if self.lbl_codigo_tarjeta.cget('text') == codigo:
                                self.after(0, lambda c=codigo: self._renderizar_abonos_desde_cache(c))
                        except Exception:
                            pass
                    except Exception as e:
                        logger.debug(f"Prefetch abonos falló para {codigo}: {e}")

            # Iniciar hilo daemon para no bloquear cierre
            t = threading.Thread(target=_worker, daemon=True)
            self._abonos_prefetch_thread = t
            t.start()
        except Exception as e:
            logger.debug(f"No se pudo iniciar prefetch de abonos: {e}")

    def _sort_abonos_asc(self, abonos: list) -> list:
        """Ordena abonos por fecha ascendente (más antiguos primero)."""
        try:
            def _key(a):
                try:
                    return datetime.fromisoformat(str(a.get('fecha', '')).replace('Z', '+00:00'))
                except Exception:
                    return datetime.min
            return sorted(abonos, key=_key, reverse=False)
        except Exception:
            return abonos

    def _build_abono_rows(self, abonos: list, tarjeta_codigo: str) -> list:
        """Convierte abonos ordenados en filas preformateadas para renderizado rápido."""
        try:
            total = len(abonos)
            filas = []
            for idx, abono in enumerate(abonos):
                try:
                    fecha_dt = datetime.fromisoformat(str(abono['fecha']).replace('Z', '+00:00'))
                    fecha_str = fecha_dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    fecha_str = str(abono.get('fecha', ''))
                try:
                    monto_str = f"$ {Decimal(abono['monto']):,.0f}"
                except Exception:
                    monto_str = str(abono.get('monto', ''))
                item_index = str(idx + 1)  # 1 = más antiguo
                filas.append((abono['id'], fecha_str, monto_str, item_index, tarjeta_codigo))
            return filas
        except Exception:
            # Si algo falla, devolver lista vacía para evitar bloquear
            return []

    def actualizar_vista_nueva_tarjeta(self, codigo_tarjeta):
        """
        [DEPRECADO por ahora] Actualiza la vista después de crear una nueva tarjeta y la resalta
        """
        logger.info(f"Actualizando vista para mostrar tarjeta nueva: {codigo_tarjeta}")
        self.mostrar_tabla_tarjetas(nueva_tarjeta_id=codigo_tarjeta)

    def setup_seccion_ver(self):
        padding_y = 8

        # Botón Ver
        ttk.Button(self.frame_central, text="Ver", padding=(0, 5)).pack(
            fill='x', padx=5, pady=padding_y)

        # Label para la fecha
        self.lbl_fecha = ttk.Label(self.frame_central, 
                                 text=datetime.now().strftime("%d/%m/%Y"))
        self.lbl_fecha.pack(padx=5, pady=padding_y)

        # Frame para cambiar tipo de tarjeta
        frame_tipo = ttk.Frame(self.frame_central)
        frame_tipo.pack(fill='x', padx=5, pady=padding_y)
        
        # Label en su propia fila
        ttk.Label(frame_tipo, text="Cambiar Tipo").pack(anchor='w')
        
        # Combobox en la siguiente fila
        self.combo_tipo = ttk.Combobox(frame_tipo, width=12,
                                      values=['activas', 'cancelada', 'pendiente'],
                                      state="readonly")
        self.combo_tipo.pack(fill='x', pady=(5,0))
        self.combo_tipo.bind('<<ComboboxSelected>>', self.cambiar_tipo_tarjeta)

        # Frame para observación
        frame_obs = ttk.Frame(self.frame_central)
        frame_obs.pack(fill='x', padx=5, pady=padding_y)
        ttk.Label(frame_obs, text="Observación").pack(anchor='w')
        self.text_observacion = tk.Text(frame_obs, height=3, width=20)
        self.text_observacion.pack(fill='x', pady=3)

        # Botones de acción con más padding
        botones = [
            ('Tarjeta Nueva', self.abrir_ventana_documento),
            ('Tarjeta Editar', self.editar_tarjeta_seleccionada),
            ('Tarjeta Eliminar', self.eliminar_tarjeta_seleccionada),
            ('Tarjeta Buscar', None),
            ('Tarjeta Mover', None),
            ('Tarjeta error', None)
        ]

        self.botones_accion = {}
        for texto, comando in botones:
            btn = ttk.Button(self.frame_central, text=texto, padding=(0, 5), command=comando)
            btn.pack(fill='x', padx=5, pady=8)
            self.botones_accion[texto] = btn

        # Activar botones de Tarjeta Nueva y Editar
        self.botones_accion['Tarjeta Nueva'].config(state=tk.NORMAL)
        self.botones_accion['Tarjeta Editar'].config(state=tk.NORMAL)

    def cambiar_tipo_tarjeta(self, event=None):
        """Cambia el tipo de la tarjeta seleccionada"""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección", "Por favor seleccione una tarjeta")
            self.combo_tipo.set('')  # Limpiar selección del combo
            return
        
        nuevo_tipo = self.combo_tipo.get()
        if not nuevo_tipo:
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar cambio",
            f"¿Seguro que quieres pasar esta tarjeta a {nuevo_tipo}?"
        )
        
        if respuesta:
            tarjeta_codigo = self.tree.item(seleccion[0], 'values')[6]
            try:
                # Actualizar el estado usando la API (por código)
                self.api_client.update_tarjeta(tarjeta_codigo, {'estado': nuevo_tipo})
                self.mostrar_tabla_tarjetas()
                messagebox.showinfo("Éxito", f"Tarjeta cambiada a estado: {nuevo_tipo}")
            except Exception as e:
                logger.error(f"Error al cambiar estado de tarjeta vía API: {e}")
                messagebox.showerror("Error de API", f"No se pudo cambiar el estado: {e}")
        else:
            self.combo_tipo.set('')

    def abrir_ventana_documento(self):
        """Abre la ventana para solicitar documento del cliente (UI existente)."""
        try:
            from ventanas.solicitar_documento import VentanaSolicitarDocumento
            VentanaSolicitarDocumento(self)
        except Exception as e:
            logger.error(f"Error al abrir ventana de documento: {e}")
            messagebox.showerror("Error", f"No se pudo abrir: {e}")

    def eliminar_tarjeta_seleccionada(self):
        """Elimina la tarjeta seleccionada en el Treeview usando la API."""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Selección Requerida", "Por favor, seleccione una tarjeta para eliminar.")
            return

        # Usar el iid tal cual (puede ser alfanumérico). Eliminar por código, no por id numérico
        item_id = seleccion[0]

        valores_item = self.tree.item(item_id, 'values')
        nombre_cliente = valores_item[2]
        apellido_cliente = valores_item[3]
        codigo_tarjeta = valores_item[6]

        confirmacion = messagebox.askyesno("Confirmar Eliminación", 
            f"¿Está seguro de que desea eliminar la tarjeta {codigo_tarjeta} \n"
            f"del cliente {nombre_cliente} {apellido_cliente}?\n"
            f"Esta acción también eliminará todos los abonos asociados y no se puede deshacer.")

        if confirmacion:
            try:
                # Llamar a la API usando el código de tarjeta
                resultado = self.api_client.delete_tarjeta(codigo_tarjeta)
                if resultado and resultado.get('ok'):
                    messagebox.showinfo("Eliminación Exitosa", f"La tarjeta {codigo_tarjeta} ha sido eliminada.")
                    self.mostrar_tabla_tarjetas()
                else:
                    error_msg = resultado.get('detail', 'Respuesta inesperada.')
                    messagebox.showerror("Error de Eliminación", f"No se pudo eliminar la tarjeta: {error_msg}")
            except Exception as e:
                logger.error(f"Error al intentar eliminar tarjeta código {codigo_tarjeta} vía API: {e}")
                messagebox.showerror("Error Crítico", f"Ocurrió un error inesperado al eliminar la tarjeta: {e}")

    def editar_tarjeta_seleccionada(self):
        """Abre la ventana de edición existente."""
        try:
            seleccion = self.tree.selection()
            if not seleccion:
                messagebox.showwarning("Selección", "Seleccione una tarjeta para editar")
                return
            codigo_tarjeta = self.tree.item(seleccion[0], 'values')[6]
            from ventanas.editar_tarjeta import VentanaEditarTarjeta
            VentanaEditarTarjeta(self, codigo_tarjeta)
        except Exception as e:
            logger.error(f"Error en ventana editar tarjeta: {e}")
            messagebox.showerror("Error", f"No se pudo abrir el formulario: {e}")

    def setup_seccion_abonos(self):
        """Configura la sección de abonos con funcionalidad completa"""
        # Frame principal para abonos
        main_frame = ttk.Frame(self.frame_derecho)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Frame superior para controles de abono
        frame_controles = ttk.LabelFrame(main_frame, text="Gestión de Abonos", padding=10)
        frame_controles.pack(fill='x', pady=(0, 10))
        
        # Primera fila: Monto y fecha
        fila1 = ttk.Frame(frame_controles)
        fila1.pack(fill='x', pady=5)
        
        ttk.Label(fila1, text="Monto:").pack(side='left', padx=(0, 5))
        self.entry_monto_abono = ttk.Entry(fila1, width=12, font=('Arial', 10, 'bold'))
        self.entry_monto_abono.pack(side='left', padx=(0, 15))
        
        ttk.Label(fila1, text="Fecha:").pack(side='left', padx=(0, 5))
        
        # Frame para fecha con botón de calendario
        frame_fecha = ttk.Frame(fila1)
        frame_fecha.pack(side='left', padx=(0, 15))
        
        self.entry_fecha_abono = ttk.Entry(frame_fecha, width=10)
        self.entry_fecha_abono.pack(side='left', padx=(0, 2))
        # Establecer fecha actual por defecto
        self.entry_fecha_abono.insert(0, datetime.now().strftime("%d/%m/%Y"))
        
        # Botón para abrir calendario
        self.btn_calendario = tk.Button(frame_fecha, text="📅", width=2, height=1,
                                      bg='#f8f9fa', fg='#495057', font=('Arial', 8),
                                      relief='raised', bd=1, cursor='hand2',
                                      command=self.abrir_calendario)
        self.btn_calendario.pack(side='left')
        
        ttk.Label(fila1, text="Código:").pack(side='left', padx=(0, 5))
        self.lbl_codigo_tarjeta = ttk.Label(fila1, text="5073", font=('Arial', 10, 'bold'), 
                                          foreground='#2E8B57')
        self.lbl_codigo_tarjeta.pack(side='left')
        
        # Segunda fila: Botones de acción
        fila2 = ttk.Frame(frame_controles)
        fila2.pack(fill='x', pady=10)
        
        # Botón Agregar (verde)
        self.btn_agregar = tk.Button(fila2, text="✓", width=3, height=1,
                                   bg='#28a745', fg='white', font=('Arial', 12, 'bold'),
                                   relief='raised', bd=2, cursor='hand2',
                                   command=self.agregar_abono)
        self.btn_agregar.pack(side='left', padx=(0, 10))
        
        # Botón Actualizar (azul)
        self.btn_actualizar = tk.Button(fila2, text="↻", width=3, height=1,
                                      bg='#007bff', fg='white', font=('Arial', 12, 'bold'),
                                      relief='raised', bd=2, cursor='hand2',
                                      command=self.actualizar_vista_abonos)
        self.btn_actualizar.pack(side='left', padx=(0, 10))
        
        # Botón Eliminar (rojo)
        self.btn_eliminar = tk.Button(fila2, text="✗", width=3, height=1,
                                    bg='#dc3545', fg='white', font=('Arial', 12, 'bold'),
                                    relief='raised', bd=2, cursor='hand2',
                                    command=self.eliminar_abono_seleccionado)
        self.btn_eliminar.pack(side='left')
        
        # Frame para la tabla de abonos
        frame_tabla_abonos = ttk.LabelFrame(main_frame, text="Historial de Abonos", padding=5)
        frame_tabla_abonos.pack(fill='both', expand=True, pady=(0, 10))
        
        # Configurar tabla de abonos con estilo mejorado
        columns = ('fecha', 'abono', 'item', 'cod_tarjeta')
        self.tabla_abonos = ttk.Treeview(frame_tabla_abonos, columns=columns, show='headings', height=8)
        
        # Configurar encabezados y anchos
        headers = {
            'fecha': 'Fecha',
            'abono': 'Abono',
            'item': 'Item',
            'cod_tarjeta': 'Cód. Tarjeta'
        }
        anchos = {'fecha': 120, 'abono': 100, 'item': 80, 'cod_tarjeta': 100}
        
        for col in columns:
            self.tabla_abonos.heading(col, text=headers[col])
            self.tabla_abonos.column(col, width=anchos[col], anchor='center')
        
        # Configurar estilo de la tabla
        style = ttk.Style()
        style.configure('Treeview', rowheight=25)
        style.configure('Treeview.Heading', font=('Arial', 9, 'bold'))
        
        # Scrollbars para la tabla
        scrollbar_y_abonos = ttk.Scrollbar(frame_tabla_abonos, orient="vertical", command=self.tabla_abonos.yview)
        scrollbar_x_abonos = ttk.Scrollbar(frame_tabla_abonos, orient="horizontal", command=self.tabla_abonos.xview)
        self.tabla_abonos.configure(yscrollcommand=scrollbar_y_abonos.set, xscrollcommand=scrollbar_x_abonos.set)
        
        # Posicionar tabla y scrollbars
        self.tabla_abonos.grid(row=0, column=0, sticky="nsew")
        scrollbar_y_abonos.grid(row=0, column=1, sticky="ns")
        scrollbar_x_abonos.grid(row=1, column=0, sticky="ew")
        
        frame_tabla_abonos.grid_rowconfigure(0, weight=1)
        frame_tabla_abonos.grid_columnconfigure(0, weight=1)
        
        # Frame para información de resumen
        frame_resumen = ttk.LabelFrame(main_frame, text="Resumen de Tarjeta", padding=10)
        frame_resumen.pack(fill='x')
        
        # Crear grid para información organizada
        self.info_labels = {}
        campos_info = [
            ('Cuotas', '-- cuota(s) de $ --'),
            ('Abono', '$ --'),
            ('Saldo', '$ --'),
            ('Cuotas pendientes a la fecha', '--'),
            ('Días pasados de cancelación', '--')
        ]
        
        for i, (campo, valor_inicial) in enumerate(campos_info):
            fila = i // 1  # Una columna
            col = (i % 1) * 2
            
            ttk.Label(frame_resumen, text=f"{campo}:", font=('Arial', 9)).grid(
                row=fila, column=col, sticky='w', padx=(0, 10), pady=2)
            
            lbl_valor = ttk.Label(frame_resumen, text=valor_inicial, font=('Arial', 9, 'bold'))
            lbl_valor.grid(row=fila, column=col+1, sticky='w', pady=2)
            self.info_labels[campo] = lbl_valor
        
        # Configurar el grid del frame de resumen
        for i in range(2):
            frame_resumen.grid_columnconfigure(i, weight=1)
        
        # Eventos de la tabla
        self.tabla_abonos.bind('<<TreeviewSelect>>', self.on_seleccion_abono)
        self.tree.bind('<<TreeviewSelect>>', self.on_seleccion_tarjeta)
        
        # Bind para Enter en el campo de monto
        self.entry_monto_abono.bind('<Return>', lambda e: self.agregar_abono())
        
        # Bind para formateo automático del monto
        self.entry_monto_abono.bind('<FocusOut>', self.formatear_numero)
        self.entry_monto_abono.bind('<KeyRelease>', self.formatear_numero_tiempo_real)
        
        # Bind para seleccionar todo al hacer clic
        self.entry_monto_abono.bind('<Button-1>', self.on_click_monto)
        self.entry_monto_abono.bind('<FocusIn>', self.on_click_monto)
        
        # Variables para tracking
        self.tarjeta_seleccionada = None
        self.abono_seleccionado = None
        
        # Cargar datos iniciales si hay una tarjeta seleccionada
        self.actualizar_vista_abonos()

    def on_seleccion_tarjeta(self, event=None):
        """Maneja la selección de una tarjeta en la tabla principal"""
        seleccion = self.tree.selection()
        if seleccion:
            # Usar el iid tal cual (puede ser código alfanumérico), no convertir a entero
            item_id = seleccion[0]
            self.tarjeta_seleccionada = item_id
            
            self.lbl_codigo_tarjeta.config(text=self.tree.item(item_id, 'values')[6]) # Mostrar código
            
            self.entry_monto_abono.delete(0, tk.END)
            self.entry_monto_abono.insert(0, "Cargando...")
            
            # Limpiar tabla de abonos
            for item in self.tabla_abonos.get_children():
                self.tabla_abonos.delete(item)
            
            # Mostrar "Cargando..." en resumen
            for label in self.info_labels.values():
                label.config(text="Cargando...", foreground='gray')
            
            self.after(50, lambda: self.cargar_datos_tarjeta_diferido(item_id))
    
    def on_seleccion_abono(self, event=None):
        """Maneja la selección de un abono en la tabla de abonos"""
        seleccion = self.tabla_abonos.selection()
        if seleccion:
            self.abono_seleccionado = int(seleccion[0])
    
    def cargar_datos_tarjeta_diferido(self, tarjeta_id):
        """Carga los datos de la tarjeta (abonos y, si está disponible, resumen)."""
        try:
            # Verificar que la tarjeta sigue seleccionada (el usuario no cambió de selección)
            if self.tarjeta_seleccionada != tarjeta_id:
                return  # El usuario ya seleccionó otra tarjeta, cancelar carga
            
            # Intentar cargar abonos primero (código de tarjeta desde label)
            codigo_tarjeta = self.lbl_codigo_tarjeta.cget('text')
            self.cargar_abonos_tarjeta(codigo_tarjeta)

            # Intentar cargar resumen si existe el método en el cliente (compatibilidad)
            resumen = None
            if hasattr(self.api_client, 'get_tarjeta_resumen'):
                try:
                    resumen = self.api_client.get_tarjeta_resumen(codigo_tarjeta)
                except Exception:
                    resumen = None
            if not resumen:
                # Si no hay resumen, dejar labels con valores por defecto
                self.entry_monto_abono.delete(0, tk.END)
                for label in self.info_labels.values():
                    label.config(text="--", foreground='black')
                return

            self.actualizar_monto_cuota_defecto(resumen)
            tarjeta_fue_cancelada = self.actualizar_resumen_tarjeta(resumen)
            
            if not tarjeta_fue_cancelada:
                self.cargar_abonos_tarjeta(codigo_tarjeta)
            
        except Exception as e:
            logger.error(f"Error en carga diferida vía API: {e}")
            self.entry_monto_abono.delete(0, tk.END)
            for label in self.info_labels.values():
                label.config(text="Error", foreground='red')
    
    def cargar_abonos_tarjeta(self, tarjeta_codigo: str):
        """Carga los abonos de una tarjeta específica desde la API (por código)."""
        try:
            for item in self.tabla_abonos.get_children():
                self.tabla_abonos.delete(item)

            # Primero intentar desde caché (filas ya preformateadas y ordenadas asc)
            filas_cache = self._abonos_cache_por_tarjeta.get(tarjeta_codigo)
            if filas_cache is None:
                # Si no está en caché, cargar en segundo plano para no bloquear la UI
                self._mostrar_loading_abonos()
                self.after(0, lambda c=tarjeta_codigo: self._fetch_abonos_async(c))
                return

            # Render desde caché (más antiguo -> más reciente)
            for fila in filas_cache:
                abono_id, fecha_str, monto_str, item_index, cod = fila
                self.tabla_abonos.insert('', 'end', iid=abono_id, values=(
                    fecha_str,
                    monto_str,
                    item_index,
                    cod
                ))
                
        except Exception as e:
            logger.error(f"Error al cargar abonos desde API: {e}")
            messagebox.showerror("Error de API", f"Error al cargar abonos: {e}")

    def _renderizar_abonos_desde_cache(self, tarjeta_codigo: str):
        """Renderiza abonos en la tabla si existen en caché para la tarjeta dada."""
        try:
            filas_cache = self._abonos_cache_por_tarjeta.get(tarjeta_codigo)
            if filas_cache is None:
                return
            for item in self.tabla_abonos.get_children():
                self.tabla_abonos.delete(item)
            for fila in filas_cache:
                abono_id, fecha_str, monto_str, item_index, cod = fila
                self.tabla_abonos.insert('', 'end', iid=abono_id, values=(
                    fecha_str,
                    monto_str,
                    item_index,
                    cod
                ))
        except Exception as e:
            logger.debug(f"No se pudo renderizar abonos desde caché para {tarjeta_codigo}: {e}")

    def _mostrar_loading_abonos(self):
        """Muestra filas placeholder mientras se cargan abonos para mejorar percepción de velocidad."""
        try:
            for item in self.tabla_abonos.get_children():
                self.tabla_abonos.delete(item)
            placeholder = [("Cargando...", "--", "--", self.lbl_codigo_tarjeta.cget('text')) for _ in range(3)]
            for idx, fila in enumerate(placeholder, 1):
                self.tabla_abonos.insert('', 'end', iid=f"loading_{idx}", values=fila)
        except Exception:
            pass

    def _fetch_abonos_async(self, tarjeta_codigo: str):
        """Descarga abonos en un hilo y actualiza caché + UI al terminar."""
        import threading
        def _worker():
            try:
                abonos = self.api_client.list_abonos_by_tarjeta(tarjeta_codigo)
                abonos = self._sort_abonos_asc(abonos)
                filas = self._build_abono_rows(abonos, tarjeta_codigo)
                self._abonos_cache_por_tarjeta[tarjeta_codigo] = filas
                # Si la tarjeta aún está visible, renderizar
                if self.lbl_codigo_tarjeta.cget('text') == tarjeta_codigo:
                    self.after(0, lambda c=tarjeta_codigo: self._renderizar_abonos_desde_cache(c))
            except Exception as e:
                logger.debug(f"Fetch abonos async falló para {tarjeta_codigo}: {e}")
        try:
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass
    
    def actualizar_resumen_tarjeta(self, resumen: dict) -> bool:
        """Actualiza la información de resumen usando los datos del endpoint de resumen de la API."""
        try:
            tarjeta_id = resumen.get('tarjeta_id') or resumen.get('codigo_tarjeta')

            # VERIFICAR SI LA TARJETA ESTÁ COMPLETAMENTE PAGADA Y ACTIVA
            estado_tarjeta = str(resumen.get('estado_tarjeta', '')).lower()
            if resumen['saldo_pendiente'] <= 0 and (estado_tarjeta == 'activa' or estado_tarjeta == 'activas'):
                logger.info(f"Tarjeta {tarjeta_id} completamente pagada. Cambiando estado a 'cancelada'")
                
                try:
                    # Enviar fecha de cancelación según la fecha del usuario (Entry de abono)
                    fecha_txt = self.entry_fecha_abono.get().strip()
                    fecha_cancel = None
                    try:
                        if fecha_txt:
                            d, m, a = fecha_txt.split('/')
                            from datetime import date as _date
                            fecha_cancel = _date(int(a), int(m), int(d))
                    except Exception:
                        fecha_cancel = None

                    payload_estado = {'estado': 'cancelada'}
                    if fecha_cancel:
                        payload_estado['fecha_cancelacion'] = fecha_cancel.isoformat()

                    self.api_client.update_tarjeta(tarjeta_id, payload_estado)
                    messagebox.showinfo("🎉 Tarjeta Cancelada", 
                                      f"¡Felicitaciones!\n\n"
                                      f"La tarjeta {resumen['codigo_tarjeta']} ha sido completamente pagada.\n"
                                      f"Estado cambiado automáticamente a 'CANCELADA'.\n\n"
                                      f"Monto total pagado: $ {Decimal(resumen['total_abonado']):,.0f}")
                    
                    self.mostrar_tabla_tarjetas()
                    
                    # Limpiar UI de abonos
                    self.tarjeta_seleccionada = None
                    self.lbl_codigo_tarjeta.config(text="--")
                    self.entry_monto_abono.delete(0, tk.END)
                    for item in self.tabla_abonos.get_children(): self.tabla_abonos.delete(item)
                    for label in self.info_labels.values(): label.config(text="--", foreground='black')
                    
                    return True # Indicar que la tarjeta fue cancelada
                except Exception as e:
                    logger.error(f"Error al cambiar estado de tarjeta {tarjeta_id} vía API: {e}")
                    messagebox.showerror("Error de API", "No se pudo actualizar el estado de la tarjeta.")
            
            # Actualizar labels con valores del resumen
            self.info_labels['Cuotas'].config(
                text=f"{resumen['cuotas_restantes']} cuota(s) de $ {Decimal(resumen['valor_cuota']):,.0f}")
            
            self.info_labels['Abono'].config(
                text=f"$ {Decimal(resumen['total_abonado']):,.0f}")
            
            saldo_pendiente = Decimal(resumen['saldo_pendiente'])
            saldo_color = '#d32f2f' if saldo_pendiente > 0 else '#2e7d32'
            self.info_labels['Saldo'].config(
                text=f"$ {saldo_pendiente:,.0f}", foreground=saldo_color)
            
            cuotas_atrasadas = resumen.get('cuotas_pendientes_a_la_fecha', 0)
            atraso_color = '#d32f2f' if cuotas_atrasadas > 0 else '#2e7d32'
            self.info_labels['Cuotas pendientes a la fecha'].config(
                text=str(cuotas_atrasadas), foreground=atraso_color)
            
            dias_vencido = resumen.get('dias_pasados_cancelacion', 0)
            vencido_color = '#d32f2f' if dias_vencido > 0 else '#2e7d32'
            self.info_labels['Días pasados de cancelación'].config(
                text=str(dias_vencido), foreground=vencido_color)
            
            return False
                
        except Exception as e:
            logger.error(f"Error al actualizar resumen con datos de API: {e}")
            for label in self.info_labels.values():
                label.config(text="Error", foreground='red')
            return False
    
    def agregar_abono(self):
        """Agrega un nuevo abono a la tarjeta seleccionada usando la API"""
        if not self.tarjeta_seleccionada:
            messagebox.showwarning("Selección", "Por favor seleccione una tarjeta")
            return
        
        try:
            monto_str = self.entry_monto_abono.get().strip()
            if not monto_str:
                messagebox.showwarning("Monto", "Por favor ingrese un monto")
                return
            
            monto = Decimal(monto_str.replace(',', '').replace('$', '').strip())
            if monto <= 0:
                messagebox.showwarning("Monto", "El monto debe ser mayor a cero")
                return
            
            # Intentar obtener resumen para validar saldo (opcional)
            saldo_pendiente = None
            if hasattr(self.api_client, 'get_tarjeta_resumen'):
                try:
                    resumen = self.api_client.get_tarjeta_resumen(self.lbl_codigo_tarjeta.cget('text'))
                    if resumen and 'saldo_pendiente' in resumen:
                        saldo_pendiente = Decimal(resumen['saldo_pendiente'])
                except Exception:
                    saldo_pendiente = None

            if saldo_pendiente is not None and monto > saldo_pendiente:
                respuesta = messagebox.askyesno(
                    "Abono Excesivo",
                    f"⚠️ ATENCIÓN ⚠️\n\n"
                    f"El abono de $ {monto:,.0f} excede el saldo pendiente de $ {saldo_pendiente:,.0f}.\n"
                    f"¿Desea ajustar el abono al saldo exacto?"
                )
                if respuesta:
                    monto = saldo_pendiente
                else:
                    return

            # Usar código de tarjeta para el API de abonos
            # Preparar fecha del usuario para el abono (dd/mm/yyyy -> ISO)
            fecha_txt = self.entry_fecha_abono.get().strip()
            fecha_iso = None
            try:
                if fecha_txt:
                    d, m, a = fecha_txt.split('/')
                    from datetime import datetime as _dt
                    fecha_iso = _dt(int(a), int(m), int(d), 12, 0, 0).isoformat()
            except Exception:
                fecha_iso = None

            abono_data = {
                "tarjeta_codigo": self.lbl_codigo_tarjeta.cget('text'),
                "monto": float(monto),
                "fecha": fecha_iso
            }
            
            nuevo_abono = self.api_client.create_abono(abono_data)
            
            if nuevo_abono and 'id' in nuevo_abono:
                self.entry_monto_abono.delete(0, tk.END)
                # Recargar todos los datos de forma diferida
                self.cargar_datos_tarjeta_diferido(self.tarjeta_seleccionada)
                
                # Solo mostrar mensaje si no se canceló (el otro método ya lo muestra)
                if saldo_pendiente is None or saldo_pendiente > 0:
                    messagebox.showinfo("✓ Abono Registrado", 
                                      f"Abono de $ {monto:,.0f} registrado correctamente.")
            else:
                error_msg = nuevo_abono.get('detail', 'Error desconocido.')
                messagebox.showerror("Error de API", f"No se pudo registrar el abono: {error_msg}")
                
        except ValueError:
            messagebox.showerror("Error", "Monto inválido. Ingrese solo números")
        except Exception as e:
            logger.error(f"Error al agregar abono vía API: {e}")
            messagebox.showerror("Error de API", f"Error al agregar abono: {e}")
    
    def formatear_numero(self, event=None):
        """Formatea automáticamente el número en el campo de monto"""
        try:
            texto = self.entry_monto_abono.get().replace(',', '').replace('$', '').strip()
            if texto and texto.replace('.', '').isdigit():
                numero = float(texto)
                self.entry_monto_abono.delete(0, tk.END)
                self.entry_monto_abono.insert(0, f"{numero:,.0f}")
        except:
            pass
    
    def formatear_numero_tiempo_real(self, event=None):
        """Formatea el número mientras se escribe, pero de forma más suave"""
        try:
            # Solo formatear si el usuario presionó espacio o tab
            if event and event.keysym in ['space', 'Tab']:
                self.formatear_numero()
        except:
            pass
    
    def eliminar_abono_seleccionado(self):
        """Elimina el abono seleccionado usando la API"""
        if not self.abono_seleccionado:
            messagebox.showwarning("Selección", "Por favor seleccione un abono para eliminar")
            return
        
        respuesta = messagebox.askyesno("Confirmar eliminación", "¿Está seguro de que desea eliminar este abono?")
        
        if respuesta:
            try:
                resultado = self.api_client.delete_abono(self.abono_seleccionado)
                
                if resultado and resultado.get('ok'):
                    self.cargar_datos_tarjeta_diferido(self.tarjeta_seleccionada)
                    self.abono_seleccionado = None
                    messagebox.showinfo("Éxito", "Abono eliminado correctamente")
                else:
                    error_msg = resultado.get('detail', 'Error desconocido.')
                    messagebox.showerror("Error de API", f"No se pudo eliminar el abono: {error_msg}")
                    
            except Exception as e:
                logger.error(f"Error al eliminar abono vía API: {e}")
                messagebox.showerror("Error de API", f"Error al eliminar abono: {e}")
    
    def actualizar_vista_abonos(self):
        """Actualiza la vista de abonos y resumen"""
        if self.tarjeta_seleccionada:
            self.cargar_datos_tarjeta_diferido(self.tarjeta_seleccionada)
    
    def actualizar_monto_cuota_defecto(self, resumen: dict):
        """Actualiza el campo de monto con el valor de la cuota por defecto desde el resumen"""
        try:
            valor_cuota = Decimal(resumen.get('valor_cuota', 0))
            self.entry_monto_abono.delete(0, tk.END)
            self.entry_monto_abono.insert(0, f"{valor_cuota:,.0f}")
        except Exception as e:
            logger.error(f"Error al actualizar monto por defecto desde resumen: {e}")
    
    def on_click_monto(self, event=None):
        """Selecciona todo el texto cuando se hace clic en el campo de monto"""
        # Usar after para evitar conflictos con el evento de clic
        self.entry_monto_abono.after(1, lambda: self.entry_monto_abono.select_range(0, tk.END))
        # No retornar 'break' para permitir edición normal
    
    def abrir_calendario(self):
        """Abre una ventana simple para seleccionar fecha"""
        try:
            # Crear ventana simple
            ventana_fecha = Toplevel(self)
            ventana_fecha.title("Seleccionar Fecha")
            ventana_fecha.geometry("300x150")
            ventana_fecha.resizable(False, False)
            ventana_fecha.grab_set()  # Modal
            
            # Centrar la ventana
            ventana_fecha.transient(self.winfo_toplevel())
            try:
                ventana_fecha.update_idletasks()
                x = (ventana_fecha.winfo_screenwidth() // 2) - (300 // 2)
                y = (ventana_fecha.winfo_screenheight() // 2) - (150 // 2)
                ventana_fecha.geometry(f"300x150+{x}+{y}")
            except Exception:
                pass
            
            # Obtener fecha actual
            try:
                fecha_str = self.entry_fecha_abono.get()
                if fecha_str and len(fecha_str) == 10:
                    partes = fecha_str.split('/')
                    dia_actual = int(partes[0])
                    mes_actual = int(partes[1])
                    año_actual = int(partes[2])
                else:
                    hoy = datetime.now()
                    dia_actual = hoy.day
                    mes_actual = hoy.month
                    año_actual = hoy.year
            except:
                hoy = datetime.now()
                dia_actual = hoy.day
                mes_actual = hoy.month
                año_actual = hoy.year
            
            # Frame principal
            main_frame = ttk.Frame(ventana_fecha, padding=20)
            main_frame.pack(fill='both', expand=True)
            
            # Título
            ttk.Label(main_frame, text="Seleccionar Fecha", 
                     font=('Arial', 12, 'bold')).pack(pady=(0, 15))
            
            # Frame para los campos
            campos_frame = ttk.Frame(main_frame)
            campos_frame.pack(pady=(0, 15))
            
            # Día
            ttk.Label(campos_frame, text="Día:").grid(row=0, column=0, padx=5, sticky='e')
            self.spin_dia = tk.Spinbox(campos_frame, from_=1, to=31, width=4, 
                                     value=dia_actual, font=('Arial', 10))
            self.spin_dia.grid(row=0, column=1, padx=5)
            
            # Mes
            ttk.Label(campos_frame, text="Mes:").grid(row=0, column=2, padx=5, sticky='e')
            self.spin_mes = tk.Spinbox(campos_frame, from_=1, to=12, width=4, 
                                     value=mes_actual, font=('Arial', 10))
            self.spin_mes.grid(row=0, column=3, padx=5)
            
            # Año
            ttk.Label(campos_frame, text="Año:").grid(row=0, column=4, padx=5, sticky='e')
            self.spin_año = tk.Spinbox(campos_frame, from_=2020, to=2030, width=6, 
                                     value=año_actual, font=('Arial', 10))
            self.spin_año.grid(row=0, column=5, padx=5)
            
            # Frame para botones
            botones_frame = ttk.Frame(main_frame)
            botones_frame.pack()
            
            # Botones
            ttk.Button(botones_frame, text="Hoy", 
                      command=lambda: self.fecha_hoy(ventana_fecha)).pack(side='left', padx=5)
            ttk.Button(botones_frame, text="Aceptar", 
                      command=lambda: self.aceptar_fecha(ventana_fecha)).pack(side='left', padx=5)
            ttk.Button(botones_frame, text="Cancelar", 
                      command=ventana_fecha.destroy).pack(side='left', padx=5)
            
        except Exception as e:
            logger.error(f"Error al abrir selector de fecha: {e}")
            messagebox.showerror("Error", f"No se pudo abrir el selector de fecha: {str(e)}")
    
    def fecha_hoy(self, ventana):
        """Establece la fecha de hoy"""
        try:
            hoy = datetime.now()
            self.spin_dia.delete(0, tk.END)
            self.spin_dia.insert(0, str(hoy.day))
            self.spin_mes.delete(0, tk.END)
            self.spin_mes.insert(0, str(hoy.month))
            self.spin_año.delete(0, tk.END)
            self.spin_año.insert(0, str(hoy.year))
        except Exception as e:
            logger.error(f"Error al establecer fecha de hoy: {e}")
    
    def aceptar_fecha(self, ventana):
        """Acepta la fecha seleccionada"""
        try:
            dia = int(self.spin_dia.get())
            mes = int(self.spin_mes.get())
            año = int(self.spin_año.get())
            
            # Validar rangos básicos
            if not (1 <= dia <= 31):
                raise ValueError("Día inválido")
            if not (1 <= mes <= 12):
                raise ValueError("Mes inválido")
            if not (2020 <= año <= 2030):
                raise ValueError("Año inválido")
            
            # Intentar crear la fecha para validar
            from datetime import date
            fecha_test = date(año, mes, dia)
            
            # Si llegamos aquí, la fecha es válida
            fecha_formateada = f"{dia:02d}/{mes:02d}/{año}"
            
            self.entry_fecha_abono.delete(0, tk.END)
            self.entry_fecha_abono.insert(0, fecha_formateada)
            ventana.destroy()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Fecha inválida: {str(e)}")
        except Exception as e:
            logger.error(f"Error al aceptar fecha: {e}")
            messagebox.showerror("Error", "Error al procesar la fecha")
            
            
            