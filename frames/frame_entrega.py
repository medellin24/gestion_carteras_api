import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
from decimal import Decimal
import logging
from tkinter import Toplevel
from tkinter import filedialog
import threading
import concurrent.futures

# Importar el cliente de la API desde la nueva ruta raíz
from api_client.client import api_client

logger = logging.getLogger(__name__)

class FrameEntrega(ttk.Frame):
    FILTROS = [
        ('todos', 'Todos'),
        ('abonos_hoy', 'Abonos del día'),
        ('excelentes', 'Clientes excelentes'),
        ('buenos', 'Clientes buenos (1-6 días)'),
        ('regulares', 'Clientes regulares (7-15 días)'),
        ('malos', 'Clientes malos (16-60 días)'),
        ('clavos', 'Clavos (>60 días)'),
    ]

    FILTRO_TAGS = {
        'abonos_hoy': ('filtro_abonos', '#86efac'),      # Verde más intenso
        'excelentes': ('filtro_excelentes', '#d8b4fe'),  # Morado más intenso
        'buenos': ('filtro_buenos', '#93c5fd'),          # Azul más intenso
        'regulares': ('filtro_regulares', '#fde047'),    # Amarillo más intenso
        'malos': ('filtro_malos', '#fb923c'),            # Naranja más intenso
        'clavos': ('filtro_clavos', '#fca5a5'),          # Rojo más intenso
    }
    def __init__(self, parent):
        super().__init__(parent)
        # Usar cliente global con token de sesión
        self.api_client = api_client
        # Zona horaria del usuario (desde token)
        try:
            tz1 = self.api_client.get_user_timezone()
            self.token_tz = tz1 or 'UTC'
        except Exception:
            self.token_tz = 'UTC'
        self.empleados_dict = {}
        # Caché de abonos por código de tarjeta
        self._abonos_cache_por_tarjeta = {}
        self._abonos_raw_cache = {}
        self._abonos_prefetch_thread = None
        self._empleado_en_prefetch = None
        # Caché de resumen por código de tarjeta
        self._resumen_cache_por_tarjeta = {}
        self._tarjetas_actuales = []
        self._tarjeta_por_iid = {}
        self._row_info = {}
        self._fecha_actual_local = date.today()
        self.filtro_actual = 'todos'
        self._filtro_label_map = {label: key for key, label in self.FILTROS}
        self._resumen_prefetch_thread = None
        
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Contraste.TFrame', background='#E0E0E0')
        # Estilos: azul bondi clarito y combobox ocre (readonly)
        style.configure('Bondi.TButton', font=('Segoe UI', 10, 'bold'), padding=(8, 5), background='#73D0E6', foreground='black')
        style.map('Bondi.TButton', background=[('active', '#4FC3D9'), ('pressed', '#4FC3D9')])
        style.configure('Ocre.TCombobox', fieldbackground='#F2C97D', background='#F2C97D', foreground='black')
        style.map('Ocre.TCombobox', fieldbackground=[('readonly', '#F2C97D')], background=[('readonly', '#F2C97D')], foreground=[('readonly', 'black')])
        self.setup_ui()
        self.cargar_empleados()

    def setup_ui(self):
        # Frame principal dividido en tres secciones con anchos específicos
        self.frame_izquierdo = ttk.LabelFrame(self, text="Cobro", width=450)  # Aumentado 1cm
        self.frame_izquierdo.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        self.frame_izquierdo.pack_propagate(False)

        self.frame_central = ttk.LabelFrame(self, text="Filtros", width=180)
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
        self.combo_empleados = ttk.Combobox(frame_seleccion, width=32, state="readonly", style='Ocre.TCombobox')
        self.combo_empleados.pack(side='left', padx=5)
        # Al abrir el combo, recargar empleados desde la API para reflejar altas recientes
        self.combo_empleados.bind('<Button-1>', lambda e: self.cargar_empleados())
        # Botón de refresco manual
        ttk.Button(frame_seleccion, text="↻", width=3, command=self.cargar_empleados).pack(side='left', padx=(0,5))
        
        self.combo_estado = ttk.Combobox(frame_seleccion, width=14, 
                                       values=['activas', 'cancelada', 'pendiente'],
                                       state="readonly", style='Ocre.TCombobox')
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
        
        # Tags de filas alternadas y tarjetas nuevas
        self.tree.tag_configure('row_even', background='white')
        self.tree.tag_configure('row_odd', background='#E6F4FA')  # Azul bondi claro
        self.tree.tag_configure('nueva', foreground='#006400')  # Verde oscuro para el texto
        for tag_name, color in self.FILTRO_TAGS.values():
            self.tree.tag_configure(tag_name, background=color)
        
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
            # Indicar carga
            try:
                self.tree.insert('', 'end', values=('', '', 'Cargando...', '', '', ''), iid='__loading__')
            except Exception:
                pass
            
            empleado_nombre = self.combo_empleados.get()
            if not empleado_nombre:
                return
            
            empleado_id = self.empleados_dict.get(empleado_nombre)
            if not empleado_id:
                return
            
            estado = self.combo_estado.get()
            # Consultar en segundo plano para no bloquear la UI
            def _worker():
                try:
                    tarjetas_loc = self.api_client.list_tarjetas(empleado_id=empleado_id, estado=estado, limit=200)
                except Exception as _e:
                    tarjetas_loc = []
                def _apply():
                    # Limpiar loading si existe
                    try:
                        if '__loading__' in self.tree.get_children():
                            self.tree.delete('__loading__')
                    except Exception:
                        pass
                    self._render_tarjetas_tabla(tarjetas_loc, nueva_tarjeta_id, empleado_id)
                try:
                    self.after(0, _apply)
                except Exception:
                    _apply()
            import threading
            threading.Thread(target=_worker, daemon=True).start()
            return

            # (este bloque no se ejecutará ya; mantenido por compatibilidad)
            # Calcular "hoy" según la zona horaria del usuario
            try:
                fecha_actual = datetime.now(ZoneInfo(self.token_tz)).date()
            except Exception:
                fecha_actual = date.today()
            
            # Limpiar caché cuando cambia empleado/estado y preparar prefetch
            self._abonos_cache_por_tarjeta = {}
            self._abonos_raw_cache = {}
            codigos_para_prefetch = []

            for idx, tarjeta in enumerate(tarjetas):
                # Preferir 'fecha' calculada por el backend; si no viene, convertir fecha_creacion a día local
                try:
                    fecha_api = tarjeta.get('fecha')
                    if fecha_api:
                        # viene como YYYY-MM-DD
                        from datetime import date as _date
                        fecha_tarjeta = _date.fromisoformat(str(fecha_api))
                    else:
                        raw_dt = tarjeta.get('fecha_creacion') or tarjeta.get('created_at')
                        dt = datetime.fromisoformat(str(raw_dt).replace('Z', '+00:00')) if raw_dt else None
                        if dt and dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        fecha_tarjeta = dt.astimezone(ZoneInfo(self.token_tz)).date() if dt else fecha_actual
                except Exception:
                    fecha_tarjeta = fecha_actual
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
                row_tag = 'row_odd' if (idx % 2) else 'row_even'
                item_id = self.tree.insert('', 'end', values=(
                    ruta_str,
                    f"${tarjeta['monto']:,.0f}",
                    nombre_cliente,
                    apellido_cliente,
                    fecha_str,
                    tarjeta['cuotas'],
                    tarjeta['codigo']
                ), iid=tarjeta.get('id', tarjeta.get('codigo')), tags=(row_tag,))

                # Acumular códigos de tarjeta para prefetch
                try:
                    cod_tar = str(tarjeta.get('codigo') or tarjeta.get('id') or '')
                    if cod_tar:
                        codigos_para_prefetch.append(cod_tar)
                except Exception:
                    pass
                
                if es_nueva:
                    # Añadir tag 'nueva' además del tag de fila
                    current_tags = list(self.tree.item(item_id, 'tags') or [])
                    if 'nueva' not in current_tags:
                        current_tags.append('nueva')
                    self.tree.item(item_id, tags=tuple(current_tags))
                
                if nueva_tarjeta_id and (tarjeta.get('id', tarjeta.get('codigo')) == nueva_tarjeta_id):
                    self.tree.selection_set(item_id)
                    self.tree.see(item_id)
                    self.tree.focus(item_id)

            # Lanzar prefetch de abonos en segundo plano (no bloquea UI)
            self._lanzar_prefetch_abonos(empleado_id, codigos_para_prefetch)
                
        except Exception as e:
            logger.error(f"Error al mostrar tarjetas desde la API: {e}")
            messagebox.showerror("Error de API", f"Error al mostrar tarjetas: {e}")

    def _render_tarjetas_tabla(self, tarjetas, nueva_tarjeta_id, empleado_id):
        """Almacena las tarjetas actuales y renderiza respetando el filtro activo."""
        try:
            self._tarjetas_actuales = list(tarjetas or [])
            try:
                self._fecha_actual_local = datetime.now(ZoneInfo(self.token_tz)).date()
            except Exception:
                self._fecha_actual_local = date.today()
            self._abonos_cache_por_tarjeta = {}
            codigos_para_prefetch = []
            for tarjeta in self._tarjetas_actuales:
                try:
                    cod_tar = str(tarjeta.get('codigo') or tarjeta.get('id') or '')
                except Exception:
                    cod_tar = ''
                if cod_tar:
                    codigos_para_prefetch.append(cod_tar)
            self._render_tarjetas_filtradas(nueva_tarjeta_id)
            if hasattr(self, 'lbl_fecha') and self._fecha_actual_local:
                try:
                    self.lbl_fecha.config(text=self._fecha_actual_local.strftime("%d/%m/%Y"))
                except Exception:
                    pass
            self._lanzar_prefetch_abonos(empleado_id, codigos_para_prefetch)
        except Exception as e:
            logger.error(f"Error al renderizar tarjetas: {e}")

    def _render_tarjetas_filtradas(self, nueva_tarjeta_id=None):
        """Pinta todas las tarjetas y aplica estilos según el filtro seleccionado."""
        try:
            try:
                if '__loading__' in self.tree.get_children():
                    self.tree.delete('__loading__')
            except Exception:
                pass
            for item in self.tree.get_children():
                self.tree.delete(item)
            self._row_info = {}
            self._tarjeta_por_iid = {}
            tarjetas = self._tarjetas_actuales or []
            fecha_actual = self._fecha_actual_local or date.today()
            self._abonos_cache_por_tarjeta = {}
            self._abonos_raw_cache = {}
            visible_idx = 0
            seleccion_iid = None
            for tarjeta in tarjetas:
                fecha_tarjeta = self._obtener_fecha_tarjeta(tarjeta, fecha_actual)
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
                cliente_obj = tarjeta.get('cliente') if isinstance(tarjeta.get('cliente'), dict) else None
                nombre_cliente = (
                    (cliente_obj.get('nombre') if cliente_obj and 'nombre' in cliente_obj else tarjeta.get('cliente_nombre', ''))
                ).upper()
                apellido_cliente = (
                    (cliente_obj.get('apellido') if cliente_obj and 'apellido' in cliente_obj else tarjeta.get('cliente_apellido', ''))
                ).upper()
                monto_str = f"${tarjeta.get('monto', 0):,.0f}"
                cuotas_str = tarjeta.get('cuotas', '')
                codigo = tarjeta.get('codigo', '')
                iid = str(tarjeta.get('id', codigo) or f"row_{visible_idx}")
                row_tag = 'row_odd' if (visible_idx % 2) else 'row_even'
                tags = [row_tag]
                if es_nueva:
                    tags.append('nueva')
                iid = str(tarjeta.get('id', codigo) or f"row_{visible_idx}")
                base_tag = 'row_odd' if (visible_idx % 2) else 'row_even'
                tags = [base_tag]
                if es_nueva:
                    tags.append('nueva')
                self.tree.insert('', 'end', values=(
                    ruta_str,
                    monto_str,
                    nombre_cliente,
                    apellido_cliente,
                    fecha_str,
                    cuotas_str,
                    codigo
                ), iid=iid, tags=tuple(tags))
                self._row_info[iid] = {'base': base_tag, 'nueva': es_nueva}
                self._tarjeta_por_iid[iid] = tarjeta
                if nueva_tarjeta_id and iid == nueva_tarjeta_id:
                    seleccion_iid = iid
                visible_idx += 1
            if visible_idx == 0:
                try:
                    self.tree.insert('', 'end', values=('', '', 'Sin resultados', '', '', ''), iid='__empty__')
                except Exception:
                    pass
            elif seleccion_iid:
                self.tree.selection_set(seleccion_iid)
                self.tree.see(seleccion_iid)
                self.tree.focus(seleccion_iid)
            self._apply_filtro_estilos()
        except Exception as e:
            logger.error(f"Error al pintar tarjetas filtradas: {e}")

    def _apply_filtro_estilos(self):
        if not self.tree or not self._row_info:
            return
        self._maybe_prefetch_resumen()
        highlight_tag = None
        if self.filtro_actual and self.filtro_actual != 'todos':
            tag_info = self.FILTRO_TAGS.get(self.filtro_actual)
            if tag_info:
                highlight_tag = tag_info[0]
                try:
                    self.tree.tag_configure(highlight_tag, background=tag_info[1])
                except Exception:
                    pass
        for iid in self.tree.get_children():
            info = self._row_info.get(iid)
            if not info:
                continue
            tags = []
            tarjeta = self._tarjeta_por_iid.get(iid)
            aplica_resaltado = (
                highlight_tag
                and tarjeta
                and self._tarjeta_cumple_filtro(tarjeta, self.filtro_actual)
            )
            if aplica_resaltado:
                tags.append(highlight_tag)
            else:
                base_tag = info.get('base', 'row_even')
                if base_tag:
                    tags.append(base_tag)
            if info.get('nueva'):
                tags.append('nueva')
            self.tree.item(iid, tags=tuple(dict.fromkeys(tags)))

    def _maybe_prefetch_resumen(self):
        filtros_resumen = {'excelentes', 'buenos', 'regulares', 'malos', 'clavos'}
        if self.filtro_actual not in filtros_resumen:
            return

        if self._resumen_prefetch_thread and self._resumen_prefetch_thread.is_alive():
            return

        # Identificar tarjetas que faltan
        pendientes = []
        for tarjeta in self._tarjetas_actuales or []:
            codigo = str(tarjeta.get('codigo') or tarjeta.get('id') or '')
            if not codigo:
                continue
            
            tiene_dias = (
                tarjeta.get('cuotas_pendientes_a_la_fecha') is not None
                or tarjeta.get('dias_atrasados') is not None
            )
            tiene_pasados = tarjeta.get('dias_pasados_cancelacion') is not None
            
            # Si ya tiene ambos datos, no necesitamos descargar
            if tiene_dias and tiene_pasados:
                continue
                
            # Si ya está en caché pero no mergeado en la tarjeta, lo mergeamos ahora
            if codigo in self._resumen_cache_por_tarjeta:
                self._merge_tarjeta_con_resumen(codigo, self._resumen_cache_por_tarjeta[codigo])
                continue
                
            pendientes.append(codigo)

        if not pendientes:
            return

        # Si hay pendientes, mostrar indicador de carga
        try:
            self.config(cursor="wait")
            if self.tree:
                self.tree.config(cursor="wait")
        except Exception:
            pass

        def _fetch_one(cod):
            try:
                res = self.api_client.get_tarjeta_resumen(cod)
                return cod, res
            except Exception:
                return cod, None

        def _worker():
            try:
                # Descarga paralela con 8 hilos
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    future_to_cod = {executor.submit(_fetch_one, c): c for c in pendientes}
                    for future in concurrent.futures.as_completed(future_to_cod):
                        c, res = future.result()
                        if res:
                            self._resumen_cache_por_tarjeta[c] = res
                            self._merge_tarjeta_con_resumen(c, res)
            except Exception as e:
                print(f"Error en prefetch paralelo: {e}")
            finally:
                # Al terminar, restaurar cursor y aplicar estilos
                def _finish():
                    self._resumen_prefetch_thread = None
                    try:
                        self.config(cursor="")
                        if self.tree:
                            self.tree.config(cursor="")
                    except Exception:
                        pass
                    self._apply_filtro_estilos()

                try:
                    self.after(0, _finish)
                except Exception:
                    pass

        self._resumen_prefetch_thread = threading.Thread(target=_worker, daemon=True)
        self._resumen_prefetch_thread.start()

    def _merge_tarjeta_con_resumen(self, codigo, resumen):
        """Enriquece la tarjeta en memoria con datos de resumen para reutilizarlos en filtros."""
        if not codigo or not resumen:
            return
        campos = ('cuotas_pendientes_a_la_fecha', 'dias_pasados_cancelacion')
        try:
            for tarjeta in self._tarjetas_actuales or []:
                if str(tarjeta.get('codigo') or tarjeta.get('id') or '') == codigo:
                    for campo in campos:
                        valor = resumen.get(campo)
                        if valor is not None:
                            tarjeta[campo] = valor
                    # Normalizar: cuotas pendientes equivale a días atrasados
                    if resumen.get('cuotas_pendientes_a_la_fecha') is not None:
                        tarjeta['dias_atrasados'] = resumen.get('cuotas_pendientes_a_la_fecha')
                    break
            for iid, tarjeta in (self._tarjeta_por_iid or {}).items():
                if str(tarjeta.get('codigo') or tarjeta.get('id') or '') == codigo:
                    for campo in campos:
                        valor = resumen.get(campo)
                        if valor is not None:
                            tarjeta[campo] = valor
                    if resumen.get('cuotas_pendientes_a_la_fecha') is not None:
                        tarjeta['dias_atrasados'] = resumen.get('cuotas_pendientes_a_la_fecha')
        except Exception:
            pass

    def _on_filtro_cambiado(self, event=None):
        label = getattr(self, 'combo_filtros', None).get() if hasattr(self, 'combo_filtros') else None
        self.filtro_actual = self._filtro_label_map.get(label, 'todos')
        self._apply_filtro_estilos()

    def _tarjeta_cumple_filtro(self, tarjeta, filtro=None):
        filtro = filtro or self.filtro_actual or 'todos'
        if filtro == 'todos' or not tarjeta:
            return False
        codigo = str(tarjeta.get('codigo') or tarjeta.get('id') or '')
        if filtro == 'abonos_hoy':
            return self._tarjeta_tiene_abono_hoy(codigo)
        dias_total = self._calcular_dias_atraso_total(codigo, tarjeta)
        if filtro == 'excelentes':
            return dias_total == 0
        if filtro == 'buenos':
            return 1 <= dias_total <= 6
        if filtro == 'regulares':
            return 7 <= dias_total <= 15
        if filtro == 'malos':
            return 16 <= dias_total <= 60
        if filtro == 'clavos':
            return dias_total > 60
        return False

    def _calcular_dias_atraso_total(self, codigo, tarjeta):
        try:
            raw_cuotas = tarjeta.get('cuotas_pendientes_a_la_fecha')
            if raw_cuotas is not None:
                # Si es negativo, son cuotas atrasadas. Si es positivo, son adelantadas (0 atraso)
                dias_atraso = abs(int(raw_cuotas)) if int(raw_cuotas) < 0 else 0
            else:
                dias_atraso = int(tarjeta.get('dias_atrasados') or 0)
        except Exception:
            dias_atraso = 0
        
        try:
            dias_pasados = int(tarjeta.get('dias_pasados_cancelacion') or 0)
        except Exception:
            dias_pasados = 0
            
        # Si no tenemos datos en la tarjeta, buscar en resumen (por si acaso no se hizo merge aun)
        resumen = self._resumen_cache_por_tarjeta.get(codigo)
        
        # Calcular días atrasados (cuotas pendientes a la fecha)
        if dias_atraso == 0:
            if resumen:
                val_resumen_cuotas = resumen.get('cuotas_pendientes_a_la_fecha')
                if val_resumen_cuotas is not None:
                    # Negativo significa atraso, positivo adelanto. Tomamos atraso absoluto.
                    dias_atraso = abs(int(val_resumen_cuotas)) if int(val_resumen_cuotas) < 0 else 0
                else:
                    dias_atraso = int(resumen.get('dias_atrasados') or 0)
            else:
                # Fallback a cálculo local aproximado si no hay resumen de API aún
                try:
                    # Usar fecha local segura para el cálculo
                    fecha_actual = self._fecha_actual_local or date.today()
                    fecha_creacion = self._obtener_fecha_tarjeta(tarjeta, fecha_actual)
                    
                    # Días transcurridos desde creación (sin contar hoy)
                    dias_transcurridos = (fecha_actual - fecha_creacion).days
                    if dias_transcurridos < 0: dias_transcurridos = 0
                    
                    # Cuotas esperadas (excluyendo domingos si fuera necesario, pero simplificado por ahora)
                    # Asumiendo pago diario lunes a sabado
                    cuotas_esperadas = dias_transcurridos
                    
                    # Cuotas pagadas (aproximado por monto)
                    monto_prestamo = float(tarjeta.get('monto') or 0)
                    total_abonado = 0 # No tenemos abonos aquí en este punto del bucle, solo tarjeta
                    # Si tuviéramos 'total_abonado' en tarjeta, podríamos usarlo.
                    # Como no es fiable sin resumen, dejamos dias_atraso en 0 o lo que venga de tarjeta
                    pass
                except Exception:
                    pass

        # Calcular días pasados de cancelación
        if dias_pasados == 0 and resumen:
             try:
                dias_pasados = int(resumen.get('dias_pasados_cancelacion') or 0)
             except Exception:
                pass
        
        # Si sigue siendo 0, intentar cálculo local para días pasados
        if dias_pasados == 0:
            try:
                fecha_actual = self._fecha_actual_local or date.today()
                fecha_creacion = self._obtener_fecha_tarjeta(tarjeta, fecha_actual)
                num_cuotas = int(tarjeta.get('cuotas') or 0)
                
                # Fecha teórica de vencimiento (sin festivos por ahora, cálculo simple)
                # Si cobro diario: fecha_creacion + cuotas (días)
                from datetime import timedelta
                fecha_vencimiento = fecha_creacion + timedelta(days=num_cuotas)
                
                delta_vencido = (fecha_actual - fecha_vencimiento).days
                if delta_vencido > 0:
                    dias_pasados = delta_vencido
            except Exception:
                pass

        return dias_atraso + max(dias_pasados, 0)

    def _tarjeta_tiene_abono_hoy(self, codigo):
        if not codigo:
            return False
        abonos = self._abonos_raw_cache.get(codigo)
        if abonos is None:
            return False
        hoy = self._fecha_actual_local or date.today()
        for abono in abonos or []:
            fecha_local = self._parse_fecha_local(abono.get('fecha') or abono.get('created_at'))
            if fecha_local == hoy:
                return True
        return False

    def _parse_fecha_local(self, raw_fecha):
        if not raw_fecha:
            return None
        try:
            if isinstance(raw_fecha, datetime):
                dt = raw_fecha
            else:
                raw_str = str(raw_fecha)
                if raw_str.endswith('Z'):
                    raw_str = raw_str.replace('Z', '+00:00')
                dt = datetime.fromisoformat(raw_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ZoneInfo(self.token_tz)).date()
        except Exception:
            try:
                return datetime.strptime(str(raw_fecha)[:10], "%Y-%m-%d").date()
            except Exception:
                return None

    def _obtener_fecha_tarjeta(self, tarjeta, default_date):
        try:
            fecha_api = tarjeta.get('fecha')
            if fecha_api:
                return date.fromisoformat(str(fecha_api))
        except Exception:
            pass
        raw_dt = tarjeta.get('fecha_creacion') or tarjeta.get('created_at')
        if raw_dt:
            try:
                dt = datetime.fromisoformat(str(raw_dt).replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(ZoneInfo(self.token_tz)).date()
            except Exception:
                pass
        return default_date

    def _lanzar_prefetch_abonos(self, empleado_id: str, codigos: list):
        """Dispara un hilo que precarga abonos para los códigos dados y los guarda en caché."""
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
                        self._abonos_raw_cache[codigo] = abonos
                        self._abonos_cache_por_tarjeta[codigo] = rows
                        if self.filtro_actual == 'abonos_hoy':
                            try:
                                self.after(0, self._apply_filtro_estilos)
                            except Exception:
                                pass
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
                    fecha_raw = str(abono.get('fecha', ''))
                    # Normalizar 'Z' a offset explícito y parsear
                    fecha_dt = datetime.fromisoformat(fecha_raw.replace('Z', '+00:00'))
                    # Si viene sin tz, asumir UTC y convertir a local
                    if fecha_dt.tzinfo is None:
                        fecha_dt = fecha_dt.replace(tzinfo=timezone.utc)
                    fecha_local = fecha_dt.astimezone()
                    fecha_str = fecha_local.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    fecha_str = fecha_raw
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

        ttk.Label(self.frame_central, text="Filtro").pack(anchor='w', padx=5, pady=(padding_y, 0))
        filtro_labels = [label for _, label in self.FILTROS]
        self.combo_filtros = ttk.Combobox(self.frame_central, values=filtro_labels, state="readonly", style='Ocre.TCombobox')
        self.combo_filtros.pack(fill='x', padx=5, pady=(0, padding_y))
        if filtro_labels:
            self.combo_filtros.current(0)
        self.combo_filtros.bind('<<ComboboxSelected>>', self._on_filtro_cambiado)

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
        self.combo_tipo = ttk.Combobox(frame_tipo, width=18,
                                      values=['activas', 'cancelada', 'pendiente'],
                                      state="readonly", style='Ocre.TCombobox')
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
            ('Importar Tarjetas', self.importar_tarjetas)
        ]

        self.botones_accion = {}
        for texto, comando in botones:
            btn = ttk.Button(self.frame_central, text=texto, style='Bondi.TButton', padding=(0, 5), command=comando)
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
        
        # Configurar estilo de la tabla y alternado para abonos
        style = ttk.Style()
        style.configure('Treeview', rowheight=25)
        style.configure('Treeview.Heading', font=('Arial', 9, 'bold'))
        self.tabla_abonos.tag_configure('row_even', background='white')
        self.tabla_abonos.tag_configure('row_odd', background='#E6F4FA')
        
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

            # Intentar usar resumen desde caché para respuesta inmediata
            resumen_cache = self._resumen_cache_por_tarjeta.get(codigo_tarjeta)
            if resumen_cache:
                self.actualizar_monto_cuota_defecto(resumen_cache)
                self._render_resumen_labels_sin_autocancel(resumen_cache)
                return

            # Intentar cargar resumen desde API
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

            # Guardar en caché y actualizar UI
            try:
                self._resumen_cache_por_tarjeta[codigo_tarjeta] = resumen
            except Exception:
                pass

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
            for idx, fila in enumerate(filas_cache):
                abono_id, fecha_str, monto_str, item_index, cod = fila
                row_tag = 'row_odd' if (idx % 2) else 'row_even'
                self.tabla_abonos.insert('', 'end', iid=abono_id, values=(
                    fecha_str,
                    monto_str,
                    item_index,
                    cod
                ), tags=(row_tag,))
                
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
            for idx, fila in enumerate(filas_cache):
                abono_id, fecha_str, monto_str, item_index, cod = fila
                row_tag = 'row_odd' if (idx % 2) else 'row_even'
                self.tabla_abonos.insert('', 'end', iid=abono_id, values=(
                    fecha_str,
                    monto_str,
                    item_index,
                    cod
                ), tags=(row_tag,))
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
            # Preparar fecha/hora LOCAL del usuario para el abono (dd/mm/yyyy -> ISO con zona horaria)
            fecha_txt = self.entry_fecha_abono.get().strip()
            from datetime import datetime as _dt
            try:
                # Usar medio día local para evitar saltos de día por conversiones de zona horaria
                tz_local = _dt.now().astimezone().tzinfo
                if fecha_txt:
                    d, m, a = fecha_txt.split('/')
                    dt_local = _dt(int(a), int(m), int(d), 12, 0, 0, tzinfo=tz_local)
                else:
                    ahora = _dt.now().astimezone()
                    dt_local = _dt(ahora.year, ahora.month, ahora.day, 12, 0, 0, tzinfo=ahora.tzinfo)
                fecha_iso = dt_local.isoformat()
            except Exception:
                # Fallback: medio día local de hoy
                ahora = _dt.now().astimezone()
                fecha_iso = _dt(ahora.year, ahora.month, ahora.day, 12, 0, 0, tzinfo=ahora.tzinfo).isoformat()

            abono_data = {
                "tarjeta_codigo": self.lbl_codigo_tarjeta.cget('text'),
                "monto": float(monto),
                "fecha": fecha_iso
            }
            
            nuevo_abono = self.api_client.create_abono(abono_data)
            
            if nuevo_abono and 'id' in nuevo_abono:
                self.entry_monto_abono.delete(0, tk.END)
                # Invalidar caché de resumen de la tarjeta actual
                try:
                    cod = self.lbl_codigo_tarjeta.cget('text')
                    if cod:
                        self._resumen_cache_por_tarjeta.pop(cod, None)
                        # Invalidar también el caché de abonos para forzar recarga desde API
                        self._abonos_cache_por_tarjeta.pop(cod, None)
                except Exception:
                    pass
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
                    # Invalidar caché de resumen de la tarjeta actual
                    try:
                        cod = self.lbl_codigo_tarjeta.cget('text')
                        if cod:
                            self._resumen_cache_por_tarjeta.pop(cod, None)
                            # Invalidar también el caché de abonos para forzar recarga desde API
                            self._abonos_cache_por_tarjeta.pop(cod, None)
                    except Exception:
                        pass
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

    def _render_resumen_labels_sin_autocancel(self, resumen: dict):
        """Actualiza labels de resumen sin ejecutar la lógica de autocancelación."""
        try:
            self.info_labels['Cuotas'].config(
                text=f"{resumen.get('cuotas_restantes', 0)} cuota(s) de $ {Decimal(resumen.get('valor_cuota', 0)):,.0f}")
            self.info_labels['Abono'].config(
                text=f"$ {Decimal(resumen.get('total_abonado', 0)):,.0f}")
            saldo_pendiente = Decimal(resumen.get('saldo_pendiente', 0))
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
        except Exception as e:
            logger.debug(f"No se pudo renderizar resumen desde caché: {e}")
    
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
            
            
            
    def importar_tarjetas(self):
        """Importa tarjetas en lote desde un archivo CSV o XLSX.
        Requiere que haya un empleado seleccionado para asociar las tarjetas.
        """
        try:
            empleado_nombre = self.combo_empleados.get().strip()
            if not empleado_nombre:
                messagebox.showwarning("Empleado requerido", "Seleccione un empleado antes de importar.")
                return
            empleado_id = self.empleados_dict.get(empleado_nombre)
            if not empleado_id:
                messagebox.showerror("Empleado inválido", "No se pudo resolver la identificación del empleado seleccionado.")
                return

            file_path = filedialog.askopenfilename(
                title="Seleccionar archivo de importación",
                filetypes=[
                    ("Archivos soportados", "*.csv *.xlsx"),
                    ("CSV", "*.csv"),
                    ("Excel", "*.xlsx"),
                    ("Todos", "*.*"),
                ]
            )
            if not file_path:
                return

            # Leer datos
            try:
                rows = self._leer_archivo_importacion(file_path)
            except ImportError:
                messagebox.showerror(
                    "Dependencia faltante",
                    "Para archivos .xlsx se requiere 'openpyxl'. Convierta a CSV o instale openpyxl."
                )
                return
            except Exception as e:
                logger.error(f"Error leyendo archivo de importación: {e}")
                messagebox.showerror("Error", f"No se pudo leer el archivo: {e}")
                return

            if not rows:
                messagebox.showwarning("Archivo vacío", "No se encontraron filas para importar.")
                return

            # Validar columnas requeridas
            requeridas_cliente = {"identificacion", "nombre", "apellido"}
            requeridas_tarjeta = {"ruta", "monto", "interes", "cuotas"}
            cols_presentes = set(rows[0].keys())
            faltantes = (requeridas_cliente | requeridas_tarjeta) - cols_presentes
            if faltantes:
                messagebox.showerror("Columnas faltantes", f"Faltan columnas obligatorias: {', '.join(sorted(faltantes))}")
                return

            # Según aclaración: el 'monto' siempre viene como TOTAL con interés incluido
            monto_es_total = True

            resumen = {
                "clientes_creados": 0,
                "tarjetas_creadas": 0,
                "abonos_creados": 0,
                "errores": 0,
            }
            errores_detalle = []

            for idx, raw in enumerate(rows, start=1):
                try:
                    identificacion = str(raw.get("identificacion") or "").strip()
                    nombre = str(raw.get("nombre") or "").strip().upper()
                    apellido = str(raw.get("apellido") or "").strip().upper()
                    telefono = str(raw.get("telefono") or "").strip() or None
                    direccion = str(raw.get("direccion") or "").strip().upper() or None
                    ruta_raw = (raw.get("ruta") if raw.get("ruta") is not None else "").__str__().strip()
                    estado_raw = str(raw.get("estado") or "").strip().lower()
                    fecha_txt = str(raw.get("fecha") or "").strip()
                    interes_raw = raw.get("interes")
                    cuotas_raw = raw.get("cuotas")
                    monto_raw = raw.get("monto")
                    abonado_raw = raw.get("abonado")

                    # Validaciones básicas
                    if not identificacion or not nombre or not apellido:
                        raise ValueError("Fila sin datos mínimos de cliente (identificacion, nombre, apellido)")

                    interes = self._to_int(interes_raw, name="interes")
                    cuotas = self._to_int(cuotas_raw, name="cuotas")
                    if cuotas <= 0:
                        raise ValueError("'cuotas' debe ser > 0")
                    monto_in = self._to_decimal(monto_raw, name="monto")
                    # Convertir a prestado (siempre viene total)
                    base = (1 + (interes or 0) / 100.0)
                    if base <= 0:
                        raise ValueError("interes inválido para convertir monto total")
                    monto_prestado = float(monto_in) / base

                    numero_ruta = self._parse_ruta(ruta_raw)
                    estado_norm = self._normalizar_estado(estado_raw) if estado_raw else "activas"
                    abonado = float(self._to_decimal(abonado_raw, allow_empty=True) or 0)

                    # fecha_creacion obligatoria para activas
                    fecha_creacion = None
                    if estado_norm == "activas":
                        if not fecha_txt:
                            raise ValueError("'fecha' es obligatoria para tarjetas activas")
                        try:
                            # Acepta dd/mm/yyyy o yyyy-mm-dd
                            if "/" in fecha_txt:
                                d, m, a = fecha_txt.split("/")
                                from datetime import datetime as _dt
                                fecha_creacion = _dt(int(a), int(m), int(d), 12, 0, 0)
                            else:
                                from datetime import datetime as _dt
                                dt = _dt.fromisoformat(fecha_txt)
                                fecha_creacion = _dt(dt.year, dt.month, dt.day, 12, 0, 0)
                        except Exception:
                            raise ValueError("'fecha' con formato inválido (use dd/mm/yyyy o yyyy-mm-dd)")

                    # Upsert Cliente
                    cliente_existente = None
                    try:
                        cliente_existente = self.api_client.get_cliente(identificacion)
                    except Exception:
                        cliente_existente = None
                    if not cliente_existente:
                        try:
                            creado = self.api_client.create_cliente({
                                "identificacion": identificacion,
                                "nombre": nombre,
                                "apellido": apellido,
                                "telefono": telefono,
                                "direccion": direccion,
                            })
                            if not (isinstance(creado, dict) and creado.get("identificacion") == identificacion):
                                # Si la API devolvió algo inesperado, verificar si ya existe ahora
                                try:
                                    chk = self.api_client.get_cliente(identificacion)
                                except Exception:
                                    chk = None
                                if chk and isinstance(chk, dict) and chk.get("identificacion") == identificacion:
                                    # Considerar como existente y continuar
                                    pass
                                else:
                                    raise RuntimeError("No se pudo crear el cliente")
                            else:
                                resumen["clientes_creados"] += 1
                        except Exception as ce:
                            # Si falló por duplicado (cliente ya existe), intentar continuar
                            try:
                                chk = self.api_client.get_cliente(identificacion)
                            except Exception:
                                chk = None
                            if chk and isinstance(chk, dict) and chk.get("identificacion") == identificacion:
                                # Cliente ya existente: continuar sin contar como error
                                pass
                            else:
                                raise

                    # Crear Tarjeta
                    nueva_tarjeta = self.api_client.create_tarjeta({
                        "cliente_identificacion": identificacion,
                        "empleado_identificacion": empleado_id,
                        "monto": float(monto_prestado),
                        "cuotas": int(cuotas),
                        "interes": int(interes),
                        "numero_ruta": float(numero_ruta) if numero_ruta is not None else None,
                        "observaciones": None,
                        "fecha_creacion": fecha_creacion,
                    })
                    codigo_tarjeta = nueva_tarjeta.get("codigo") if isinstance(nueva_tarjeta, dict) else None
                    if not codigo_tarjeta:
                        raise RuntimeError("No se pudo crear la tarjeta")
                    resumen["tarjetas_creadas"] += 1

                    # Actualizar estado si viene definido y es distinto a 'activas'
                    if estado_norm and estado_norm != "activas":
                        try:
                            self.api_client.update_tarjeta(codigo_tarjeta, {"estado": estado_norm})
                        except Exception:
                            # No bloquear por fallo de estado
                            pass

                    # Crear abono inicial si aplica
                    if abonado > 0:
                        try:
                            _ = self.api_client.create_abono({
                                "tarjeta_codigo": codigo_tarjeta,
                                "monto": float(abonado),
                                "metodo_pago": "efectivo",
                            })
                            resumen["abonos_creados"] += 1
                        except Exception:
                            errores_detalle.append(f"Fila {idx}: abono falló para tarjeta {codigo_tarjeta}")
                            resumen["errores"] += 1

                except Exception as e:
                    resumen["errores"] += 1
                    if len(errores_detalle) < 10:
                        errores_detalle.append(f"Fila {idx}: {e}")

            # Actualizar UI
            self.mostrar_tabla_tarjetas()

            # Mostrar resumen
            detalle_txt = "\n".join(errores_detalle)
            mensaje = (
                f"Clientes creados: {resumen['clientes_creados']}\n"
                f"Tarjetas creadas: {resumen['tarjetas_creadas']}\n"
                f"Abonos creados: {resumen['abonos_creados']}\n"
                f"Errores: {resumen['errores']}"
            )
            if detalle_txt:
                mensaje += f"\n\nDetalles (primeros 10):\n{detalle_txt}"
            messagebox.showinfo("Importación finalizada", mensaje)

        except Exception as e:
            logger.error(f"Error en importación masiva: {e}")
            messagebox.showerror("Error", f"Error en importación: {e}")

    def _leer_archivo_importacion(self, path: str) -> list:
        """Lee un archivo CSV o XLSX y devuelve una lista de dicts con claves normalizadas.
        Claves esperadas: ruta, identificacion, nombre, apellido, fecha, monto, cuotas, abonado, estado, telefono, direccion, interes
        """
        import os
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            return self._leer_csv(path)
        elif ext == ".xlsx":
            # Requiere openpyxl
            try:
                import openpyxl  # noqa: F401
            except Exception as e:
                raise ImportError("openpyxl no disponible")
            return self._leer_xlsx(path)
        else:
            raise ValueError("Formato no soportado. Use CSV o XLSX")

    def _normalizar_headers(self, headers: list) -> list:
        norm = []
        for h in headers:
            if h is None:
                norm.append("")
                continue
            s = str(h).strip().lower()
            norm.append(s)
        return norm

    def _leer_csv(self, path: str) -> list:
        import csv
        rows = []
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if not headers:
                return []
            headers = self._normalizar_headers(headers)
            for r in reader:
                if not any(str(c or "").strip() for c in r):
                    continue
                row = {}
                for i, h in enumerate(headers):
                    if not h:
                        continue
                    row[h] = r[i] if i < len(r) else None
                rows.append(row)
        return rows

    def _leer_xlsx(self, path: str) -> list:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb.active
        rows = []
        headers = None
        for ridx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if ridx == 1:
                headers = self._normalizar_headers(list(row or []))
                continue
            if not headers:
                break
            if not any(str(c or "").strip() for c in (row or [])):
                continue
            d = {}
            for i, h in enumerate(headers):
                if not h:
                    continue
                val = row[i] if i < len(row or []) else None
                d[h] = val
            rows.append(d)
        return rows

    def _to_decimal(self, value, name: str = "valor", allow_empty: bool = False):
        from decimal import Decimal as _Dec, InvalidOperation
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if allow_empty:
                return None
            raise ValueError(f"'{name}' vacío")
        if isinstance(value, (int, float)):
            return _Dec(str(value))
        s = str(value).replace("$", "").replace(",", "").replace(" ", "").replace(".", "", 0)
        # Conserva último punto como separador decimal si aplica
        try:
            return _Dec(str(value).replace("$", "").replace(",", "").replace(" ", ""))
        except InvalidOperation:
            raise ValueError(f"'{name}' no es numérico")

    def _to_int(self, value, name: str = "valor") -> int:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            raise ValueError(f"'{name}' vacío")
        try:
            if isinstance(value, float):
                return int(round(value))
            return int(str(value).strip())
        except Exception:
            raise ValueError(f"'{name}' no es entero válido")

    def _parse_ruta(self, ruta_raw: str):
        try:
            if not ruta_raw:
                return None
            r = str(ruta_raw).strip()
            if r.isdigit():
                return int(r)
            # Intentar float entero
            return int(float(r))
        except Exception:
            return None

    def _normalizar_estado(self, estado: str) -> str:
        e = (estado or "").strip().lower()
        if e in ("activa", "activas"):
            return "activas"
        if e in ("cancelada", "canceladas"):
            return "cancelada"
        if e in ("pendiente", "pendientes"):
            return "pendiente"
        return "activas"