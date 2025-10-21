import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import logging
from decimal import Decimal
from tkcalendar import DateEntry
import threading
import time
import winsound
from typing import List, Dict
import unicodedata

# Importar el cliente de la API desde la nueva ruta raíz
from api_client.client import api_client

# Importar ventana de edición de tarjeta
from ventanas.editar_tarjeta import VentanaEditarTarjeta

logger = logging.getLogger(__name__)

class FrameLiquidacion(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        
        # Usar cliente global con token de sesión
        self.api_client = api_client
        
        # Variables
        self.empleados_dict = {}
        self.tipos_gastos_dict = {}
        self.gasto_seleccionado = None
        self.empleado_actual_id = None
        self.fecha_actual = date.today()
        
        # Cachés para enriquecer datos sin repetir llamadas
        self._abono_cache = {}
        self._tarjeta_cache = {}
        self._detalles_abiertos = {}
        
        self.setup_ui()
        self.cargar_empleados()
        self.cargar_tipos_gastos()
        
        # Estado inicial - mostrar que se debe generar liquidación
        self.limpiar_datos_liquidacion()

    def setup_ui(self):
        """Configura la interfaz según el diseño de la imagen proporcionada"""
        
        # Configurar estilos
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Segoe UI', 10, 'bold'))
        style.configure('Value.TLabel', font=('Segoe UI', 10, 'bold'), foreground='#2563EB')
        style.configure('Money.TLabel', font=('Segoe UI', 11, 'bold'), foreground='#059669')
        style.configure('Total.TLabel', font=('Segoe UI', 14, 'bold'), foreground='#DC2626')
        # Estilo Ocre robusto para Combobox y estilos extra
        style.configure('Ocre.TCombobox', fieldbackground='#F2C97D', background='#F2C97D', foreground='black')
        style.map('Ocre.TCombobox', fieldbackground=[('readonly', '#F2C97D')], background=[('readonly', '#F2C97D')], foreground=[('readonly', 'black')])
        style.configure('OcreRobust.TCombobox', fieldbackground='#F2C97D', background='#F2C97D', foreground='black', padding=(8, 6))
        style.map('OcreRobust.TCombobox', fieldbackground=[('readonly', '#F2C97D')], background=[('readonly', '#F2C97D')], foreground=[('readonly', 'black')])
        # Variante con fuente más grande para el Combobox de empleado
        style.configure('OcreRobustBig.TCombobox', fieldbackground='#F2C97D', background='#F2C97D', foreground='black', padding=(8, 6), font=('Segoe UI', 14))
        style.map('OcreRobustBig.TCombobox', fieldbackground=[('readonly', '#F2C97D')], background=[('readonly', '#F2C97D')], foreground=[('readonly', 'black')])
        # Labelframes blancos para stats y cálculos
        style.configure('White.TLabelframe', background='#FFFFFF')
        style.configure('White.TLabelframe.Label', background='#FFFFFF', foreground='#111827')
        # Treeview de gastos con fuente más bonita y tamaño mayor
        style.configure('Gastos.Treeview', font=('Segoe UI', 10))
        style.configure('Gastos.Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        # Estilo para tablas de detalle (encabezado rojo cereza, filas alternadas, scrollbar delgado)
        style.configure('Detalle.Treeview', font=('Segoe UI', 10), rowheight=24)
        style.configure('Detalle.Treeview.Heading', font=('Segoe UI', 10, 'bold'), background='#C2185B', foreground='white')
        style.map('Detalle.Treeview', background=[('selected', '#0078d4')], foreground=[('selected', 'white')])
        
        # Container principal con padding
        main_container = ttk.Frame(self, padding=15)
        main_container.pack(fill='both', expand=True)
        
        # SECCIÓN SUPERIOR: Selección de empleado y fecha
        header_frame = ttk.LabelFrame(main_container, text="Selección de Empleado y Fecha", padding=8)
        header_frame.pack(fill='x', pady=(0, 15))
        
        # Configurar grid del header
        header_frame.grid_columnconfigure(1, weight=1)
        header_frame.grid_columnconfigure(3, weight=1)
        
        # Empleado
        ttk.Label(header_frame, text="Empleado:", style='Header.TLabel').grid(
            row=0, column=0, sticky='w', padx=(0, 10))
        self.combo_empleado = ttk.Combobox(header_frame, width=9, state='readonly', style='OcreRobustBig.TCombobox')
        self.combo_empleado.grid(row=0, column=1, sticky='ew', padx=(0, 20))
        try:
            self.combo_empleado.set('▼ Elige empleado')
        except Exception:
            pass
        self.combo_empleado.bind('<<ComboboxSelected>>', self.on_empleado_seleccionado)
        # Recargar empleados al abrir el combo para reflejar cambios recientes
        self.combo_empleado.bind('<Button-1>', lambda e: self.cargar_empleados())
        # Botón de refresco manual
        ttk.Button(header_frame, text='↻', width=3, command=self.cargar_empleados).grid(row=0, column=1, sticky='e')
        
        # Fecha con calendario
        ttk.Label(header_frame, text="Fecha:", style='Header.TLabel').grid(
            row=0, column=2, sticky='w', padx=(0, 10))
        
        fecha_frame = ttk.Frame(header_frame)
        fecha_frame.grid(row=0, column=3, sticky='ew')
        
        # Usar DateEntry para mostrar un calendario
        self.date_picker = DateEntry(fecha_frame, 
                                   width=14, 
                                   background='darkblue',
                                   foreground='white', 
                                   borderwidth=2,
                                   date_pattern='dd/mm/yyyy',
                                   locale='es_ES',
                                   font=('Segoe UI', 11))
        self.date_picker.pack(side='left', padx=(0, 10))
        self.date_picker.set_date(self.fecha_actual)
        self.date_picker.bind('<<DateEntrySelected>>', self.on_fecha_cambio)
        
        # PANEL PRINCIPAL: 3 columnas según la imagen
        main_panel = ttk.Frame(main_container)
        main_panel.pack(fill='both', expand=True, pady=(0, 15))
        
        # Configurar proporciones según la imagen
        main_panel.grid_columnconfigure(0, weight=2, minsize=200)  # Estadísticas - más ancho
        main_panel.grid_columnconfigure(1, weight=3, minsize=300)  # Finanzas - el más ancho
        main_panel.grid_columnconfigure(2, weight=2, minsize=200)  # Gestión - igual que estadísticas
        main_panel.grid_rowconfigure(0, weight=1)
        
        # COLUMNA 1: Estadísticas de Tarjetas
        stats_frame = ttk.LabelFrame(main_panel, text="Estadísticas de Tarjetas", padding=15, style='White.TLabelframe')
        stats_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        
        # Estadísticas con mejor espaciado
        stats_data = [
            ("Tarjetas Activas:", "tarjetas_activas"),
            ("Tarjetas Canceladas:", "tarjetas_canceladas"),
            ("Tarjetas Nuevas:", "tarjetas_nuevas"),
            ("Total Abonos:", "total_registros")
        ]
        
        self.labels_estadisticas = {}
        
        for i, (texto, key) in enumerate(stats_data):
            row_bg = '#E6F4FA' if (i % 2) else '#FFFFFF'
            frame_row = tk.Frame(stats_frame, bg=row_bg)
            frame_row.pack(fill='x', pady=2)
            tk.Label(frame_row, text=texto, font=('Segoe UI', 10, 'bold'), bg=row_bg).pack(side='left')
            lbl_valor = tk.Label(frame_row, text="0", font=('Segoe UI', 10, 'bold'), fg='#2563EB', bg=row_bg)
            lbl_valor.pack(side='right')
            if key != 'tarjetas_activas':
                lbl_valor.configure(cursor='hand2')
                lbl_valor.bind('<Button-1>', lambda e, stat_key=key: self.mostrar_detalle_estadistica(stat_key))
                lbl_valor.bind('<Enter>', lambda e, lbl=lbl_valor: lbl.configure(fg='#1E40AF'))
                lbl_valor.bind('<Leave>', lambda e, lbl=lbl_valor: lbl.configure(fg='#2563EB'))
            self.labels_estadisticas[key] = lbl_valor
        
        # COLUMNA 2: Cálculos Financieros (la más ancha)
        calc_frame = ttk.LabelFrame(main_panel, text="Cálculos Financieros", padding=15, style='White.TLabelframe')
        calc_frame.grid(row=0, column=1, sticky='nsew', padx=(0, 10))
        
        # Cálculos financieros con mejor presentación
        calc_data = [
            ("Total Recaudado:", "total_recaudado"),
            ("Base del Día:", "base_dia"),
            ("Préstamos Otorgados:", "prestamos_otorgados"),
            ("Total Gastos:", "total_gastos")
        ]
        
        self.labels_calculos = {}
        
        for i, (texto, key) in enumerate(calc_data):
            row_bg = '#E6F4FA' if (i % 2) else '#FFFFFF'
            frame_row = tk.Frame(calc_frame, bg=row_bg)
            frame_row.pack(fill='x', pady=2)
            tk.Label(frame_row, text=texto, font=('Segoe UI', 10, 'bold'), bg=row_bg).pack(side='left')
            lbl_valor = tk.Label(frame_row, text="$ 0", font=('Segoe UI', 11, 'bold'), fg='#059669', bg=row_bg)
            lbl_valor.pack(side='right')
            self.labels_calculos[key] = lbl_valor

            # Agregar desglose bajo Total Recaudado
            if key == 'total_recaudado':
                # Efectivo
                fila_efectivo = tk.Frame(calc_frame, bg='#E6F4FA') # Alternar color
                fila_efectivo.pack(fill='x', pady=2, padx=(16, 0))
                tk.Label(fila_efectivo, text="Efectivo:", font=('Segoe UI', 10, 'bold'), bg='#E6F4FA').pack(side='left')
                lbl_efectivo = tk.Label(fila_efectivo, text="$ 0", font=('Segoe UI', 11, 'bold'), fg='#059669', bg='#E6F4FA')
                lbl_efectivo.pack(side='right')
                self.labels_calculos['recaudado_efectivo'] = lbl_efectivo
                # Abrir detalle de efectivo al hacer clic
                lbl_efectivo.configure(cursor='hand2')
                lbl_efectivo.bind('<Button-1>', lambda e: self.mostrar_detalle_recaudos_metodo('efectivo'))
                lbl_efectivo.bind('<Enter>', lambda e, lbl=lbl_efectivo: lbl.configure(fg='#047857'))
                lbl_efectivo.bind('<Leave>', lambda e, lbl=lbl_efectivo: lbl.configure(fg='#059669'))

                # Consignación
                fila_consig = tk.Frame(calc_frame, bg='#FFFFFF') # Alternar color
                fila_consig.pack(fill='x', pady=1, padx=(16, 0))
                tk.Label(fila_consig, text="Consignación:", font=('Segoe UI', 10, 'bold'), bg='#FFFFFF').pack(side='left')
                lbl_consig = tk.Label(fila_consig, text="$ 0", font=('Segoe UI', 11, 'bold'), fg='#059669', bg='#FFFFFF')
                lbl_consig.pack(side='right')
                self.labels_calculos['recaudado_consignacion'] = lbl_consig
                # Abrir detalle de consignación al hacer clic
                lbl_consig.configure(cursor='hand2')
                lbl_consig.bind('<Button-1>', lambda e: self.mostrar_detalle_recaudos_metodo('consignacion'))
                lbl_consig.bind('<Enter>', lambda e, lbl=lbl_consig: lbl.configure(fg='#047857'))
                lbl_consig.bind('<Leave>', lambda e, lbl=lbl_consig: lbl.configure(fg='#059669'))
        
        # Línea separadora y total final
        ttk.Separator(calc_frame, orient='horizontal').pack(fill='x', pady=8)
        
        total_frame = ttk.Frame(calc_frame)
        total_frame.pack(fill='x', pady=6)
        
        ttk.Label(total_frame, text="TOTAL FINAL:", 
                font=('Segoe UI', 12, 'bold')).pack(side='left')
        
        lbl_total = ttk.Label(total_frame, text="$ 0", style='Total.TLabel')
        lbl_total.pack(side='right')
        self.labels_calculos['total_final'] = lbl_total

        # (Depuración eliminada)
        
        # COLUMNA 3: Gestión de Base
        base_frame = ttk.LabelFrame(main_panel, text="Gestión de Base", padding=10)
        base_frame.grid(row=0, column=2, sticky='nsew')
        
        # Frame para contenido dinámico de la base
        self.base_frame = base_frame
        self.base_content_frame = ttk.Frame(base_frame)
        self.base_content_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Botón de generar liquidación (mismas dimensiones que asignar base)
        self.btn_generar_liquidacion = tk.Button(base_frame, text="💰 Generar Liquidación",
                                               bg='#10B981', fg='white', font=('Segoe UI', 10, 'bold'),
                                               command=self.generar_liquidacion)
        self.btn_generar_liquidacion.pack(fill='x', pady=6)
        
        # SECCIÓN INFERIOR: Gestión de Gastos (dos columnas)
        gastos_frame = ttk.LabelFrame(main_container, text="Gestión de Gastos", padding=10)
        gastos_frame.pack(fill='both', expand=True)
        
        gastos_content = ttk.Frame(gastos_frame)
        gastos_content.pack(fill='both', expand=True)
        gastos_content.grid_columnconfigure(0, weight=3)
        gastos_content.grid_columnconfigure(1, weight=1)
        gastos_content.grid_rowconfigure(0, weight=1)

        # Tabla de gastos (izquierda)
        tree_frame = ttk.Frame(gastos_content)
        tree_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        # Configurar Treeview
        columns = ('Tipo', 'Descripción', 'Valor')
        self.tree_gastos = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10, style='Gastos.Treeview')
        
        # Configurar columnas
        self.tree_gastos.heading('Tipo', text='Tipo de Gasto')
        self.tree_gastos.heading('Descripción', text='Descripción')
        self.tree_gastos.heading('Valor', text='Valor')
        
        self.tree_gastos.column('Tipo', width=150)
        self.tree_gastos.column('Descripción', width=250)
        self.tree_gastos.column('Valor', width=100)
        scrollbar_gastos = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree_gastos.yview)
        self.tree_gastos.configure(yscrollcommand=scrollbar_gastos.set)
        self.tree_gastos.pack(side='left', fill='both', expand=True)
        scrollbar_gastos.pack(side='right', fill='y')

        # Acciones y total (derecha)
        actions_frame = ttk.Frame(gastos_content)
        actions_frame.grid(row=0, column=1, sticky='ns')
        self.btn_agregar_gasto = tk.Button(actions_frame, text="Agregar Gasto", 
                                         bg='#059669', fg='white', font=('Arial', 10, 'bold'),
                                         command=self.agregar_gasto_nuevo)
        self.btn_agregar_gasto.pack(fill='x', pady=(0, 8))
        self.btn_editar_gasto = tk.Button(actions_frame, text="Editar", 
                                        bg='#F59E0B', fg='white', font=('Arial', 10, 'bold'),
                                        command=self.editar_gasto_seleccionado)
        self.btn_editar_gasto.pack(fill='x', pady=(0, 8))
        self.btn_eliminar_gasto = tk.Button(actions_frame, text="Eliminar", 
                                          bg='#DC2626', fg='white', font=('Arial', 10, 'bold'),
                                          command=self.eliminar_gasto_seleccionado)
        self.btn_eliminar_gasto.pack(fill='x')
        ttk.Separator(actions_frame, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(actions_frame, text="Total Gastos:", style='Header.TLabel').pack(anchor='w')
        self.lbl_total_gastos_dia = ttk.Label(actions_frame, text="$ 0", style='Money.TLabel')
        self.lbl_total_gastos_dia.pack(anchor='w')
        
        # Eventos
        self.tree_gastos.bind('<<TreeviewSelect>>', self.on_gasto_seleccionado)
        self.tree_gastos.bind('<Double-1>', self.editar_gasto_seleccionado)

    def cargar_empleados(self):
        """Carga la lista de empleados desde la API."""
        try:
            empleados = self.api_client.list_empleados()
            if empleados:
                # El diccionario ahora guarda nombre_completo: identificacion
                self.empleados_dict = {
                    emp['nombre_completo']: emp['identificacion'] for emp in empleados
                }
                self.combo_empleado['values'] = list(self.empleados_dict.keys())
                logger.info(f"Cargados {len(empleados)} empleados correctamente desde la API")
        except Exception as e:
            logger.error(f"Error al cargar empleados desde la API: {e}")
            messagebox.showerror("Error de API", f"No se pudieron cargar los empleados: {e}")

    def cargar_tipos_gastos(self):
        """Carga los tipos de gastos desde la API."""
        try:
            tipos = self.api_client.list_tipos_gastos()
            # Guardar el diccionario completo para referencia futura
            self.tipos_gastos_dict = {tipo['nombre']: tipo for tipo in tipos}
            logger.info(f"Cargados {len(tipos)} tipos de gastos correctamente desde la API")
        except Exception as e:
            logger.error(f"Error al cargar tipos de gastos desde la API: {e}")
            messagebox.showerror("Error de API", f"No se pudieron cargar los tipos de gastos: {e}")

    def on_empleado_seleccionado(self, event=None):
        """Maneja la selección de empleado - SIN actualización automática"""
        empleado_nombre = self.combo_empleado.get()
        if empleado_nombre and empleado_nombre in self.empleados_dict:
            self.empleado_actual_id = self.empleados_dict[empleado_nombre]
            
            # ✅ SOLO actualizar interfaz básica, NO los cálculos
            self.limpiar_datos_liquidacion()
            self.actualizar_interfaz_base()
            self.cargar_gastos_del_dia()
            
            logger.info(f"Empleado seleccionado: {empleado_nombre} (ID: {self.empleado_actual_id})")

    def on_fecha_cambio(self, event=None):
        """Maneja el cambio de fecha del calendario - SIN actualización automática"""
        try:
            # Obtener fecha del DateEntry
            self.fecha_actual = self.date_picker.get_date()
            
            # ✅ SOLO limpiar datos y cargar gastos, NO calcular liquidación
            if self.empleado_actual_id:
                self.limpiar_datos_liquidacion()
                self.actualizar_interfaz_base()
                self.cargar_gastos_del_dia()
            
            logger.info(f"Fecha cambiada a: {self.fecha_actual}")
        except Exception as e:
            logger.error(f"Error al cambiar fecha: {e}")
            messagebox.showerror("Error", "Error al cambiar la fecha")

    def limpiar_datos_liquidacion(self):
        """Limpia los datos de liquidación mostrados en la interfaz"""
        # Limpiar estadísticas
        for label in self.labels_estadisticas.values():
            label.config(text="--", foreground='#6B7280')
        
        # Limpiar cálculos financieros
        for label in self.labels_calculos.values():
            label.config(text="--", foreground='#6B7280')
        
        # Mostrar mensaje indicativo
        self.labels_calculos['total_final'].config(
            text="Presione 'Generar Liquidación'", 
            foreground='#3B82F6'
        )

    def actualizar_liquidacion(self):
        """Actualiza todos los datos de liquidación usando la API."""
        if not self.empleado_actual_id:
            return
        
        try:
            # La fecha debe enviarse en formato ISO (YYYY-MM-DD)
            fecha_str = self.fecha_actual.strftime('%Y-%m-%d')
            datos = self.api_client.get_liquidacion_diaria(self.empleado_actual_id, fecha_str)
            
            # Actualizar estadísticas
            for key, label in self.labels_estadisticas.items():
                valor = datos.get(key, 0)
                label.config(text=str(valor))
            
            # Actualizar cálculos financieros
            for key, label in self.labels_calculos.items():
                # Evitar sobreescribir las etiquetas de desglose aquí; se actualizan abajo
                if key in ('recaudado_efectivo', 'recaudado_consignacion'):
                    continue
                # Convertir los valores a Decimal para el formato
                valor = Decimal(datos.get(key, '0'))
                
                texto = f"$ {valor:,.0f}"
                if valor < 0:
                    label.config(foreground='#EF4444')
                elif key == 'total_final':
                    label.config(foreground='#1E40AF')
                else:
                    label.config(foreground='#059669')
                label.config(text=texto)

            # Calcular y mostrar desglose de recaudado por método de pago
            try:
                fecha_str = self.fecha_actual.strftime('%Y-%m-%d')
                abonos_dia = self.api_client.list_abonos_del_dia(self.empleado_actual_id, fecha_str)
                total_efectivo = Decimal(0)
                total_consig = Decimal(0)
                for abono in abonos_dia:
                    monto = Decimal(str(abono.get('monto', 0)))
                    metodo_raw = self._obtener_metodo_pago(abono)
                    metodo_norm = self._normalizar_texto(metodo_raw).strip().lower()
                    abono_id = abono.get('id') or abono.get('abono_id') or 's/n'
                    # Si no viene el método en la lista, intentar enriquecer con el endpoint individual
                    if not metodo_norm and abono_id != 's/n':
                        try:
                            abono_id_int = int(abono_id)
                            abono_full = self.api_client.get_abono(abono_id_int)
                            metodo_raw_full = self._obtener_metodo_pago(abono_full)
                            if metodo_raw_full:
                                metodo_raw = metodo_raw_full
                                metodo_norm = self._normalizar_texto(metodo_raw_full).strip().lower()
                        except Exception as _:
                            pass
                    if 'consignacion' in metodo_norm:
                        total_consig += monto
                    elif 'efectivo' in metodo_norm:
                        total_efectivo += monto
                if 'recaudado_efectivo' in self.labels_calculos:
                    self.labels_calculos['recaudado_efectivo'].config(text=f"$ {total_efectivo:,.0f}")
                if 'recaudado_consignacion' in self.labels_calculos:
                    self.labels_calculos['recaudado_consignacion'].config(text=f"$ {total_consig:,.0f}")
            except Exception as e:
                logger.error(f"Error al calcular desglose de recaudado: {e}")
            
            # Actualizar interfaz dinámica de base y gastos
            self.actualizar_interfaz_base()
            self.cargar_gastos_del_dia()
            logger.info(f"Liquidación actualizada para el empleado ID {self.empleado_actual_id}")
            
        except Exception as e:
            logger.error(f"Error al actualizar liquidación desde la API: {e}")
            messagebox.showerror("Error de API", f"Error al actualizar liquidación: {e}")

    def cargar_gastos_del_dia(self):
        """Carga los gastos del día actual desde la API."""
        if not self.empleado_actual_id:
            return
        
        try:
            # Limpiar tabla
            for item in self.tree_gastos.get_children():
                self.tree_gastos.delete(item)
            
            fecha_str = self.fecha_actual.strftime('%Y-%m-%d')
            gastos = self.api_client.list_gastos(empleado_id=self.empleado_actual_id, fecha=fecha_str)
            
            total_gastos = Decimal(0)
            
            for gasto in gastos:
                valor = Decimal(gasto['valor'])
                total_gastos += valor

                tipo_mostrar = gasto.get('tipo_gasto_nombre') or gasto.get('tipo') or gasto.get('tipo_nombre', '')
                self.tree_gastos.insert('', 'end', iid=gasto['id'], values=(
                    tipo_mostrar,
                    gasto.get('observacion') or '',
                    f"$ {valor:,.0f}"
                ))
            
            # Actualizar total
            self.lbl_total_gastos_dia.config(text=f"$ {total_gastos:,.0f}")
            
        except Exception as e:
            logger.error(f"Error al cargar gastos desde la API: {e}")
            messagebox.showerror("Error de API", f"No se pudieron cargar los gastos: {e}")

    def agregar_gasto_nuevo(self):
        """Agrega un nuevo gasto mediante ventana modal y la API."""
        if not self.empleado_actual_id:
            messagebox.showwarning("Advertencia", "Seleccione un empleado")
            return
        
        # Ventana modal para agregar gasto
        ventana_agregar = tk.Toplevel(self)
        ventana_agregar.title("➕ Agregar Nuevo Gasto")
        ventana_agregar.geometry("400x280")
        ventana_agregar.resizable(False, False)
        ventana_agregar.transient(self.winfo_toplevel())
        ventana_agregar.grab_set()
        try:
            ventana_agregar.update_idletasks()
            x = (ventana_agregar.winfo_screenwidth() // 2) - (400 // 2)
            y = (ventana_agregar.winfo_screenheight() // 2) - (280 // 2)
            ventana_agregar.geometry("400x280+%d+%d" % (x, y))
        except Exception:
            pass
        
        frame_agregar = ttk.Frame(ventana_agregar, padding=20)
        frame_agregar.pack(fill='both', expand=True)
        
        ttk.Label(frame_agregar, text="Agregar Nuevo Gasto", 
                font=('Segoe UI', 12, 'bold')).pack(pady=(0, 15))
        
        # Formulario
        fields_frame = ttk.Frame(frame_agregar)
        fields_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(fields_frame, text="Tipo de Gasto:").grid(row=0, column=0, sticky='w', pady=5)
        combo_tipo = ttk.Combobox(fields_frame, values=list(self.tipos_gastos_dict.keys()), 
                                state='readonly', width=20)
        combo_tipo.grid(row=0, column=1, sticky='ew', padx=(10, 0), pady=5)
        
        ttk.Label(fields_frame, text="Valor:").grid(row=1, column=0, sticky='w', pady=5)
        entry_valor = ttk.Entry(fields_frame, width=20)
        entry_valor.grid(row=1, column=1, sticky='ew', padx=(10, 0), pady=5)
        
        ttk.Label(fields_frame, text="Descripción:").grid(row=2, column=0, sticky='w', pady=5)
        entry_desc = ttk.Entry(fields_frame, width=20)
        entry_desc.grid(row=2, column=1, sticky='ew', padx=(10, 0), pady=5)
        
        fields_frame.grid_columnconfigure(1, weight=1)
        
        def guardar_gasto():
            try:
                tipo_nombre = combo_tipo.get()
                if not tipo_nombre:
                    messagebox.showwarning("Advertencia", "Seleccione un tipo de gasto")
                    return
                
                valor_str = entry_valor.get().strip()
                if not valor_str:
                    messagebox.showwarning("Advertencia", "Ingrese el valor del gasto")
                    return
                
                valor = Decimal(valor_str.replace(',', '').replace('$', ''))
                if valor <= 0:
                    messagebox.showwarning("Advertencia", "El valor debe ser mayor a cero")
                    return
                
                observacion = entry_desc.get().strip() or None
                
                gasto_data = {
                    "empleado_identificacion": self.empleado_actual_id,
                    "tipo": tipo_nombre,
                    "valor": float(valor),
                    "fecha": self.fecha_actual.strftime('%Y-%m-%d'),
                    "observacion": observacion
                }
                
                nuevo_gasto = self.api_client.create_gasto(gasto_data)
                
                if nuevo_gasto and 'id' in nuevo_gasto:
                    messagebox.showinfo("Éxito", "Gasto agregado correctamente")
                    ventana_agregar.destroy()
                    self.cargar_gastos_del_dia()
                else:
                    messagebox.showerror("Error", f"No se pudo agregar el gasto: {nuevo_gasto.get('detail', 'Error desconocido')}")
                    
            except ValueError:
                messagebox.showerror("Error", "Valor inválido. Ingrese solo números")
            except Exception as e:
                logger.error(f"Error al agregar gasto vía API: {e}")
                messagebox.showerror("Error de API", f"Error al agregar gasto: {e}")
        
        # Botones
        frame_botones = ttk.Frame(frame_agregar)
        frame_botones.pack()
        
        tk.Button(frame_botones, text="💾 Guardar", bg='#059669', fg='white',
                font=('Segoe UI', 10, 'bold'), command=guardar_gasto).pack(side='left', padx=5)
        
        tk.Button(frame_botones, text="❌ Cancelar", bg='#DC2626', fg='white',
                font=('Segoe UI', 10, 'bold'), command=ventana_agregar.destroy).pack(side='left', padx=5)

    def on_gasto_seleccionado(self, event=None):
        """Maneja la selección de un gasto"""
        seleccion = self.tree_gastos.selection()
        if seleccion:
            self.gasto_seleccionado = int(seleccion[0])
        else:
            self.gasto_seleccionado = None

    def editar_gasto_seleccionado(self, event=None):
        """Edita el gasto seleccionado"""
        if not self.gasto_seleccionado:
            messagebox.showwarning("Advertencia", "Seleccione un gasto para editar")
            return
        
        item = self.tree_gastos.item(self.gasto_seleccionado)
        if not item['values']:
            return
        
        tipo_actual, obs_actual, valor_actual = item['values']
        gasto_id = self.gasto_seleccionado
        
        # Ventana de edición moderna
        ventana_editar = tk.Toplevel(self)
        ventana_editar.title("✏️ Editar Gasto")
        ventana_editar.geometry("400x250")
        ventana_editar.resizable(False, False)
        ventana_editar.transient(self.winfo_toplevel())
        ventana_editar.grab_set()
        try:
            ventana_editar.update_idletasks()
            x = (ventana_editar.winfo_screenwidth() // 2) - (400 // 2)
            y = (ventana_editar.winfo_screenheight() // 2) - (250 // 2)
            ventana_editar.geometry("400x250+%d+%d" % (x, y))
        except Exception:
            pass
        
        frame_editar = ttk.Frame(ventana_editar, padding=20)
        frame_editar.pack(fill='both', expand=True)
        
        ttk.Label(frame_editar, text=f"Editando Gasto ID: {gasto_id}", 
                font=('Segoe UI', 12, 'bold')).pack(pady=(0, 15))
        
        # Formulario
        fields_frame = ttk.Frame(frame_editar)
        fields_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(fields_frame, text="Tipo:").grid(row=0, column=0, sticky='w', pady=5)
        combo_edit_tipo = ttk.Combobox(fields_frame, values=list(self.tipos_gastos_dict.keys()), 
                                     state='readonly', width=20)
        combo_edit_tipo.set(tipo_actual)
        combo_edit_tipo.grid(row=0, column=1, sticky='ew', padx=(10, 0), pady=5)
        
        ttk.Label(fields_frame, text="Valor:").grid(row=1, column=0, sticky='w', pady=5)
        entry_edit_valor = ttk.Entry(fields_frame, width=20)
        valor_limpio = valor_actual.replace('$', '').replace(',', '').strip()
        entry_edit_valor.insert(0, valor_limpio)
        entry_edit_valor.grid(row=1, column=1, sticky='ew', padx=(10, 0), pady=5)
        
        ttk.Label(fields_frame, text="Observación:").grid(row=2, column=0, sticky='w', pady=5)
        entry_edit_obs = ttk.Entry(fields_frame, width=20)
        if obs_actual and obs_actual != "":
            entry_edit_obs.insert(0, obs_actual)
        entry_edit_obs.grid(row=2, column=1, sticky='ew', padx=(10, 0), pady=5)
        
        fields_frame.grid_columnconfigure(1, weight=1)
        
        def guardar_cambios():
            try:
                nuevo_tipo_nombre = combo_edit_tipo.get()
                if not nuevo_tipo_nombre:
                    messagebox.showwarning("Advertencia", "Seleccione un tipo de gasto")
                    return
                
                nuevo_valor_str = entry_edit_valor.get().strip()
                if not nuevo_valor_str:
                    messagebox.showwarning("Advertencia", "Ingrese el valor del gasto")
                    return
                
                nuevo_valor = Decimal(nuevo_valor_str.replace(',', '').replace('$', ''))
                if nuevo_valor <= 0:
                    messagebox.showwarning("Advertencia", "El valor debe ser mayor a cero")
                    return
                
                nueva_obs = entry_edit_obs.get().strip() or None
                
                gasto_data = {
                    "tipo": nuevo_tipo_nombre,
                    "valor": float(nuevo_valor),
                    "observacion": nueva_obs
                }
                
                gasto_actualizado = self.api_client.update_gasto(gasto_id, gasto_data)
                
                if gasto_actualizado and 'id' in gasto_actualizado:
                    messagebox.showinfo("Éxito", "Gasto actualizado correctamente")
                    ventana_editar.destroy()
                    self.cargar_gastos_del_dia()
                else:
                    messagebox.showerror("Error", f"No se pudo actualizar el gasto: {gasto_actualizado.get('detail', 'Error desconocido')}")
                    
            except ValueError:
                messagebox.showerror("Error", "Valor inválido. Ingrese solo números")
            except Exception as e:
                logger.error(f"Error al actualizar gasto vía API: {e}")
                messagebox.showerror("Error de API", f"Error al actualizar: {e}")
        
        # Botones
        frame_botones = ttk.Frame(frame_editar)
        frame_botones.pack()
        
        tk.Button(frame_botones, text="💾 Guardar", bg='#10B981', fg='white',
                font=('Segoe UI', 10, 'bold'), command=guardar_cambios).pack(side='left', padx=5)
        
        tk.Button(frame_botones, text="❌ Cancelar", bg='#EF4444', fg='white',
                font=('Segoe UI', 10, 'bold'), command=ventana_editar.destroy).pack(side='left', padx=5)

    def eliminar_gasto_seleccionado(self):
        """Elimina el gasto seleccionado"""
        if not self.gasto_seleccionado:
            messagebox.showwarning("Advertencia", "Seleccione un gasto para eliminar")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar Eliminación",
            "¿Está seguro de que desea eliminar este gasto?\nEsta acción no se puede deshacer."
        )
        
        if respuesta:
            try:
                resultado = self.api_client.delete_gasto(self.gasto_seleccionado)
                
                # La API devuelve un mensaje de éxito en un diccionario
                if resultado and resultado.get('ok'):
                    self.gasto_seleccionado = None
                    self.cargar_gastos_del_dia()
                    messagebox.showinfo("Éxito", "Gasto eliminado correctamente")
                else:
                    error_msg = resultado.get('detail', 'Respuesta inesperada de la API.')
                    messagebox.showerror("Error", f"No se pudo eliminar el gasto: {error_msg}")
            except Exception as e:
                logger.error(f"Error al eliminar gasto vía API: {e}")
                messagebox.showerror("Error de API", f"Error al eliminar gasto: {e}")

    def generar_liquidacion(self):
        """Genera la liquidación final con ventana de carga"""
        if not self.empleado_actual_id:
            messagebox.showwarning("Advertencia", "Seleccione un empleado")
            return
        
        # Crear ventana de carga mejorada
        self.mostrar_ventana_carga()
        
        # Ejecutar la consulta en un hilo separado para no bloquear la UI
        threading.Thread(target=self._procesar_liquidacion, daemon=True).start()
    
    def mostrar_ventana_carga(self):
        """Muestra una ventana de carga mientras se procesa la liquidación"""
        self.ventana_carga = tk.Toplevel(self)
        self.ventana_carga.title("Generando Liquidación")
        self.ventana_carga.geometry("350x140")
        self.ventana_carga.resizable(False, False)
        self.ventana_carga.transient(self.winfo_toplevel())
        self.ventana_carga.grab_set()
        
        # Centrar la ventana
        self.ventana_carga.update_idletasks()
        x = (self.ventana_carga.winfo_screenwidth() // 2) - (350 // 2)
        y = (self.ventana_carga.winfo_screenheight() // 2) - (140 // 2)
        self.ventana_carga.geometry(f"350x140+{x}+{y}")
        
        # Contenido de la ventana
        frame_carga = ttk.Frame(self.ventana_carga, padding=20)
        frame_carga.pack(fill='both', expand=True)
        
        # Icono y texto
        ttk.Label(frame_carga, text="💰", font=('Segoe UI', 24)).pack(pady=(0, 5))
        ttk.Label(frame_carga, text="Generando Liquidación", 
                font=('Segoe UI', 12, 'bold')).pack()
        ttk.Label(frame_carga, text="Por favor espere...", 
                font=('Segoe UI', 10), foreground='#6B7280').pack(pady=(5, 0))
        
        # Barra de progreso indeterminada
        self.progress_bar = ttk.Progressbar(frame_carga, mode='indeterminate')
        self.progress_bar.pack(fill='x', pady=(15, 0))
        self.progress_bar.start(10)  # Velocidad de animación
    
    def _procesar_liquidacion(self):
        """Procesa la liquidación en hilo separado"""
        try:
            # Simular tiempo de procesamiento mínimo para que se vea la ventana
            time.sleep(0.5)
            
            # Actualizar los datos de liquidación
            self.actualizar_liquidacion()
            
            # Cerrar ventana de carga y reproducir sonido en el hilo principal
            self.after(0, self._finalizar_liquidacion)
            
        except Exception as e:
            logger.error(f"Error al generar liquidación: {e}")
            self.after(0, lambda: self._error_liquidacion(str(e)))
    
    def _finalizar_liquidacion(self):
        """Finaliza el proceso de liquidación en el hilo principal"""
        try:
            # Cerrar ventana de carga
            if hasattr(self, 'ventana_carga') and self.ventana_carga.winfo_exists():
                self.progress_bar.stop()
                self.ventana_carga.destroy()
            
            # Reproducir sonido de confirmación
            try:
                winsound.MessageBeep(winsound.MB_OK)  # Sonido de confirmación de Windows
            except:
                # Si falla el sonido, continuar sin error
                pass
            
        except Exception as e:
            logger.error(f"Error al finalizar liquidación: {e}")
    
    def _error_liquidacion(self, error_msg):
        """Maneja errores en la liquidación"""
        try:
            # Cerrar ventana de carga
            if hasattr(self, 'ventana_carga') and self.ventana_carga.winfo_exists():
                self.progress_bar.stop()
                self.ventana_carga.destroy()
            
            # Mostrar error
            messagebox.showerror("Error", f"Error al generar liquidación: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error al manejar error de liquidación: {e}")

    def mostrar_detalle_estadistica(self, tipo_estadistica):
        """Muestra ventana con detalles desde la API según el tipo: tarjetas_canceladas, tarjetas_nuevas, total_registros (abonos)."""
        if not self.empleado_actual_id:
            messagebox.showwarning("Advertencia", "Seleccione un empleado")
            return
        fecha_str = self.fecha_actual.strftime('%Y-%m-%d')

        try:
            if tipo_estadistica == 'tarjetas_canceladas':
                items = self.api_client.list_tarjetas_canceladas_del_dia(self.empleado_actual_id, fecha_str)
                titulo = "Tarjetas canceladas del día"
                cols = ("Cliente", "Cancelado", "Monto", "Ruta")
                filas = []
                abonos_idx = self._build_abonos_index_por_tarjeta(fecha_str)
                for t in items:
                    cliente_dict = t.get('cliente') or {}
                    apellido = str(cliente_dict.get('apellido') or t.get('cliente_apellido') or '')
                    nombre = str(cliente_dict.get('nombre') or t.get('cliente_nombre') or '')
                    cliente = f"{apellido} {nombre}".strip().upper()
                    cancelado = self._first_number(t, ('valor_cancelado', 'total_abonos', 'abonado_total', 'total_pagado', 'pagado', 'abonos'))
                    if cancelado == 0:
                        codigo_tarjeta = self._get_tarjeta_codigo_from_data(t)
                        abono_final = abonos_idx.get(codigo_tarjeta)
                        if abono_final:
                            cancelado = self._first_number(abono_final, ('monto', 'valor'))
                    monto = self._first_number(t, ('monto', 'valor_prestamo', 'monto_prestamo'))
                    ruta = str(t.get('numero_ruta') or t.get('ruta') or t.get('numeroRuta') or '')
                    filas.append((cliente, f"$ {cancelado:,.0f}", f"$ {monto:,.0f}", ruta))
            elif tipo_estadistica == 'tarjetas_nuevas':
                items = self.api_client.list_tarjetas_nuevas_del_dia(self.empleado_actual_id, fecha_str)
                titulo = "Tarjetas nuevas del día"
                cols = ("Cliente", "Teléfono", "Dirección", "Monto", "Fecha", "Interés", "Cuotas", "Ruta")
                filas = []
                for t in items:
                    c = t.get('cliente') or {}
                    apellido = str(c.get('apellido') or t.get('cliente_apellido') or '')
                    nombre = str(c.get('nombre') or t.get('cliente_nombre') or '')
                    cliente = f"{apellido} {nombre}".strip().upper()
                    telefono = self._get_first_str(c, ('telefono', 'celular', 'telefono1', 'movil')) or self._get_first_str(t, ('telefono', 'celular'))
                    direccion = self._get_first_str(c, ('direccion', 'direccion_residencia')) or self._get_first_str(t, ('direccion',))
                    if not (telefono and direccion):
                        t_codigo = self._get_tarjeta_codigo_from_data(t)
                        t_id = self._get_tarjeta_id_from_data(t)
                        tarjeta_full = self._get_tarjeta_with_cache(codigo=t_codigo, tarjeta_id=t_id)
                        if tarjeta_full:
                            tel2, dir2 = self._extract_contacto_from_tarjeta(tarjeta_full)
                            if not telefono:
                                telefono = tel2
                            if not direccion:
                                direccion = dir2
                    monto = self._first_number(t, ('monto', 'valor_prestamo', 'monto_prestamo'))
                    fecha_txt = self._parse_iso_date_only(t.get('fecha') or t.get('fecha_creacion') or t.get('created_at'))
                    interes = self._first_number(t, ('interes', 'tasa', 'tasa_interes'))
                    interes_txt = f"{interes}%" if interes else ''
                    cuotas = str(t.get('cuotas') or t.get('num_cuotas') or '')
                    ruta = str(t.get('numero_ruta') or t.get('ruta') or '')
                    filas.append((cliente, telefono, direccion, f"$ {monto:,.0f}", fecha_txt, interes_txt, cuotas, ruta))
            elif tipo_estadistica == 'total_registros':
                items = self.api_client.list_abonos_del_dia(self.empleado_actual_id, fecha_str)
                titulo = "Abonos del día"
                cols = ("Cliente", "Abonado", "Método", "Monto", "Fecha")
                filas = []
                for a in items:
                    apellido = str(a.get('cliente_apellido') or a.get('apellido') or '')
                    nombre = str(a.get('cliente_nombre') or a.get('nombre') or '')
                    cliente = f"{apellido} {nombre}".strip().upper()
                    abonado = self._first_number(a, ('monto', 'valor'))
                    metodo_raw = self._obtener_metodo_pago(a)
                    if not (metodo_raw and str(metodo_raw).strip()):
                        a_id = a.get('id') or a.get('abono_id')
                        if a_id:
                            a_full = self._get_abono_with_cache(a_id)
                            if a_full:
                                metodo_raw = self._obtener_metodo_pago(a_full) or metodo_raw
                                if self._first_number(a_full, ('monto', 'valor')) and abonado == 0:
                                    abonado = self._first_number(a_full, ('monto', 'valor'))
                                if self._extraer_monto_prestamo_de_abono(a_full) is not None:
                                    monto_prestamo = self._extraer_monto_prestamo_de_abono(a_full)
                                else:
                                    t_codigo = self._get_tarjeta_codigo_from_data(a_full)
                                    t_id = self._get_tarjeta_id_from_data(a_full)
                                    t_full = self._get_tarjeta_with_cache(codigo=t_codigo, tarjeta_id=t_id)
                                    monto_prestamo = self._first_number(t_full or {}, ('monto', 'monto_prestamo')) if t_full else None
                            else:
                                monto_prestamo = self._extraer_monto_prestamo_de_abono(a)
                    else:
                        monto_prestamo = self._extraer_monto_prestamo_de_abono(a)
                        if monto_prestamo is None:
                            t_codigo = self._get_tarjeta_codigo_from_data(a)
                            t_id = self._get_tarjeta_id_from_data(a)
                            t_full = self._get_tarjeta_with_cache(codigo=t_codigo, tarjeta_id=t_id)
                            monto_prestamo = self._first_number(t_full or {}, ('monto', 'monto_prestamo')) if t_full else None
                    metodo_norm = self._normalizar_texto(metodo_raw).lower()
                    metodo_txt = 'Consignación' if 'consignacion' in metodo_norm else ('Efectivo' if 'efectivo' in metodo_norm else (metodo_raw or ''))
                    fecha_txt = self._parse_iso_date_only(a.get('fecha') or a.get('created_at'))
                    filas.append((cliente, f"$ {abonado:,.0f}", metodo_txt, f"$ {monto_prestamo:,.0f}" if monto_prestamo else "", fecha_txt))
            else:
                messagebox.showinfo("Info", "Detalle no disponible para esta estadística.")
                return

            self._mostrar_tabla_detalle(titulo, cols, filas, raw_items=items, contexto=('abonos_dia' if tipo_estadistica == 'total_registros' else tipo_estadistica))
        except Exception as e:
            logger.error(f"Error al cargar detalle de {tipo_estadistica}: {e}")
            messagebox.showerror("Error", f"No se pudo cargar el detalle: {e}")

    def _mostrar_tabla_detalle(self, titulo, columnas, filas, raw_items=None, contexto=None):
        ventana = tk.Toplevel(self)
        ventana.title(titulo)
        # Registrar ventana abierta por contexto
        try:
            if contexto:
                self._detalles_abiertos[contexto] = ventana
        except Exception:
            pass
        # Tamaño dinámico: si son 2 columnas (efectivo/consignación), usar ventana compacta
        ancho, alto = (360, 320) if len(columnas) <= 2 else (700, 400)
        ventana.geometry(f"{ancho}x{alto}")
        ventana.resizable(True, True)
        ventana.transient(self.winfo_toplevel())
        ventana.grab_set()
        try:
            ventana.update_idletasks()
            x = (ventana.winfo_screenwidth() // 2) - (ancho // 2)
            y = (ventana.winfo_screenheight() // 2) - (alto // 2)
            ventana.geometry(f"{ancho}x{alto}+%d+%d" % (x, y))
        except Exception:
            pass

        def _on_close():
            try:
                if contexto and contexto in self._detalles_abiertos and self._detalles_abiertos[contexto] is ventana:
                    del self._detalles_abiertos[contexto]
            except Exception:
                pass
            ventana.destroy()
        ventana.protocol("WM_DELETE_WINDOW", _on_close)

        cont = ttk.Frame(ventana, padding=10)
        cont.pack(fill='both', expand=True)

        tree = ttk.Treeview(cont, columns=columnas, show='headings', style='Detalle.Treeview')
        for idx, col in enumerate(columnas):
            tree.heading(col, text=col)
            if len(columnas) <= 2:
                # Ventanas compactas (Efectivo/Consignación)
                if idx == 0:
                    tree.column(col, width=200, anchor='w', stretch=False)
                else:
                    tree.column(col, width=120, anchor='e', stretch=False)
            else:
                base_width = 140 if len(columnas) < 6 else 120
                if idx == 0:
                    tree.column(col, width=base_width + 80, anchor='w', stretch=True)
                else:
                    tree.column(col, width=base_width, anchor='center', stretch=True)
        vs = tk.Scrollbar(cont, orient='vertical', command=tree.yview, width=8)
        hs = tk.Scrollbar(cont, orient='horizontal', command=tree.xview, width=8)
        tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        tree.pack(side='top', fill='both', expand=True)
        vs.pack(side='right', fill='y')
        hs.pack(side='bottom', fill='x')

        tree.tag_configure('row_even', background='#FFFFFF')
        tree.tag_configure('row_odd', background='#E6F4FA')

        # Insertar filas y mapear iids a índices de raw_items
        iid_to_index = {}
        for i, fila in enumerate(filas):
            tag = 'row_odd' if (i % 2) else 'row_even'
            iid = f"row-{i}"
            tree.insert('', 'end', iid=iid, values=fila, tags=(tag,))
            iid_to_index[iid] = i

        # Menú contextual
        menu = tk.Menu(ventana, tearoff=0)
        menu.add_command(label="Modificar", command=lambda: on_modificar())
        menu.add_command(label="Eliminar", command=lambda: on_eliminar())

        def get_selected_raw():
            sel = tree.selection()
            if not sel:
                return None
            idx = iid_to_index.get(sel[0])
            if idx is None:
                return None
            if raw_items and 0 <= idx < len(raw_items):
                return raw_items[idx]
            return None

        def on_modificar():
            try:
                raw = get_selected_raw()
                if not raw:
                    messagebox.showinfo("Info", "Seleccione un registro")
                    return
                if contexto in ("tarjetas_nuevas", "tarjetas_canceladas"):
                    codigo = self._get_tarjeta_codigo_from_data(raw)
                    if not codigo:
                        messagebox.showerror("Error", "No se pudo determinar el código de la tarjeta.")
                        return
                    VentanaEditarTarjeta(self.winfo_toplevel(), codigo)
                    # Nota: VentanaEditarTarjeta maneja su propio guardado; tras cerrarse refrescamos
                    self._abono_cache.clear(); self._tarjeta_cache.clear(); self._refrescar_ventanas_detalle()
                else:
                    # Abonos: abrir editor simple
                    abono_id = raw.get('id') or raw.get('abono_id')
                    if not abono_id:
                        messagebox.showerror("Error", "No se pudo determinar el ID del abono.")
                        return
                    editar_abono(abono_id)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo modificar: {e}")

        def on_eliminar():
            try:
                raw = get_selected_raw()
                if not raw:
                    messagebox.showinfo("Info", "Seleccione un registro")
                    return
                # Solo permitir eliminar en tarjetas nuevas y abonos (según indicación)
                if contexto == "tarjetas_nuevas":
                    codigo = self._get_tarjeta_codigo_from_data(raw)
                    if not codigo:
                        messagebox.showerror("Error", "No se pudo determinar el código de la tarjeta.")
                        return
                    if messagebox.askyesno("Confirmar", f"¿Eliminar tarjeta {codigo}?"):
                        resp = self.api_client.delete_tarjeta(codigo)
                        messagebox.showinfo("Resultado", "Tarjeta eliminada" if resp else "Acción completada")
                        # Quitar del Treeview
                        sel = tree.selection()
                        if sel:
                            tree.delete(sel[0])
                        self._abono_cache.clear(); self._tarjeta_cache.clear(); self._refrescar_ventanas_detalle()
                elif contexto in ("abonos_dia", "efectivo", "consignacion"):
                    abono_id = raw.get('id') or raw.get('abono_id')
                    if not abono_id:
                        messagebox.showerror("Error", "No se pudo determinar el ID del abono.")
                        return
                    if messagebox.askyesno("Confirmar", f"¿Eliminar abono #{abono_id}?"):
                        resp = self.api_client.delete_abono(int(abono_id))
                        messagebox.showinfo("Resultado", "Abono eliminado" if resp else "Acción completada")
                        sel = tree.selection()
                        if sel:
                            tree.delete(sel[0])
                        self._abono_cache.clear(); self._tarjeta_cache.clear(); self._refrescar_ventanas_detalle()
                else:
                    messagebox.showinfo("Info", "Eliminación no disponible para esta vista.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar: {e}")

        def editar_abono(abono_id):
            # Cargar abono para mostrar valores actuales
            ab = self._get_abono_with_cache(abono_id) or {}
            dlg = tk.Toplevel(ventana)
            dlg.title(f"Editar Abono #{abono_id}")
            dlg.geometry("300x200")
            dlg.resizable(False, False)
            dlg.transient(ventana)
            dlg.grab_set()
            frame = ttk.Frame(dlg, padding=12)
            frame.pack(fill='both', expand=True)
            ttk.Label(frame, text="Monto:").grid(row=0, column=0, sticky='w', pady=6)
            entry_monto = ttk.Entry(frame, width=18)
            try:
                monto_actual = ab.get('monto') or ab.get('valor') or ''
                entry_monto.insert(0, str(monto_actual))
            except Exception:
                pass
            entry_monto.grid(row=0, column=1, sticky='ew', pady=6)
            ttk.Label(frame, text="Método:").grid(row=1, column=0, sticky='w', pady=6)
            combo_metodo = ttk.Combobox(frame, state='readonly', values=["Efectivo", "Consignación"], width=16)
            metodo_raw = self._obtener_metodo_pago(ab)
            metodo_norm = self._normalizar_texto(metodo_raw).lower()
            if 'consignacion' in metodo_norm:
                combo_metodo.set('Consignación')
            elif 'efectivo' in metodo_norm:
                combo_metodo.set('Efectivo')
            else:
                combo_metodo.set('Efectivo')
            combo_metodo.grid(row=1, column=1, sticky='ew', pady=6)
            frame.grid_columnconfigure(1, weight=1)

            def guardar():
                try:
                    monto_str = entry_monto.get().strip()
                    monto = float(str(monto_str).replace(',', '').replace('$', '')) if monto_str else None
                    metodo_sel = combo_metodo.get()
                    metodo_api = 'efectivo' if metodo_sel.lower().startswith('efec') else 'consignacion'
                    payload = {}
                    if monto is not None:
                        payload['monto'] = monto
                    payload['metodo_pago'] = metodo_api
                    if not payload:
                        messagebox.showinfo("Info", "Sin cambios que guardar")
                        return
                    resp = self.api_client.update_abono(int(abono_id), payload)
                    # Actualizar fila seleccionada
                    sel = tree.selection()
                    if sel:
                        # Recalcular valores visibles según columnas
                        vals = list(tree.item(sel[0], 'values'))
                        try:
                            # Abonado es col 1, Método col 2
                            vals[1] = f"$ {Decimal(str(monto)):,.0f}" if monto is not None else vals[1]
                            vals[2] = 'Efectivo' if metodo_api == 'efectivo' else 'Consignación'
                        except Exception:
                            pass
                        tree.item(sel[0], values=tuple(vals))
                    messagebox.showinfo("Éxito", "Abono actualizado")
                    self._abono_cache.clear(); self._tarjeta_cache.clear(); self._refrescar_ventanas_detalle()
                    dlg.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo actualizar: {e}")

            btns = ttk.Frame(frame)
            btns.grid(row=2, column=0, columnspan=2, pady=(10, 0))
            ttk.Button(btns, text="Guardar", command=guardar).pack(side='left', padx=5)
            ttk.Button(btns, text="Cancelar", command=dlg.destroy).pack(side='left', padx=5)

        def mostrar_menu(event):
            try:
                row_id = tree.identify_row(event.y)
                if row_id:
                    tree.selection_set(row_id)
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        # Bind botón derecho
        tree.bind('<Button-3>', mostrar_menu)

    def mostrar_detalle_tarjetas_canceladas(self):
        """[DESACTIVADO] Muestra ventana con lista de tarjetas canceladas"""
        messagebox.showinfo("Función en Desarrollo",
                          "La vista detallada de tarjetas canceladas se está actualizando y estará disponible próximamente.")

    def mostrar_detalle_tarjetas_nuevas(self):
        """[DESACTIVADO] Muestra ventana con lista de tarjetas creadas hoy"""
        messagebox.showinfo("Función en Desarrollo",
                          "La vista detallada de tarjetas nuevas se está actualizando y estará disponible próximamente.")

    def mostrar_detalle_abonos_dia(self):
        """[DESACTIVADO] Muestra ventana con lista de abonos del día"""
        messagebox.showinfo("Función en Desarrollo",
                          "La vista detallada de abonos del día se está actualizando y estará disponible próximamente.")

    # --- Funciones auxiliares de detalles también desactivadas ---

    def mostrar_detalle_tarjetas(self, parent, tipo):
        """[DESACTIVADO] Muestra el detalle de tarjetas según el tipo"""
        messagebox.showinfo("Función en Desarrollo",
                          "Las vistas de detalles se están actualizando.")

    def mostrar_detalle_abonos(self, parent):
        """[DESACTIVADO] Muestra el detalle de abonos del día"""
        messagebox.showinfo("Función en Desarrollo",
                          "Las vistas de detalles se están actualizando.")

    def mostrar_detalle_recaudos_metodo(self, metodo: str):
        """Muestra ventana emergente con abonos del día filtrados por método (efectivo/consignacion)."""
        if not self.empleado_actual_id:
            messagebox.showwarning("Advertencia", "Seleccione un empleado")
            return
        metodo_norm = (self._normalizar_texto(metodo) or '').strip().lower()
        titulo = "Recaudos en Efectivo (día)" if 'efectivo' in metodo_norm else "Recaudos en Consignación (día)"
        fecha_str = self.fecha_actual.strftime('%Y-%m-%d')
        try:
            items = self.api_client.list_abonos_del_dia(self.empleado_actual_id, fecha_str)
            columnas = ("Cliente", "Abono")
            filas = []
            raw_filtrados = []
            for a in items:
                m_raw = self._obtener_metodo_pago(a)
                m_norm = self._normalizar_texto(m_raw).lower()
                if not m_norm:
                    # Fallback: enriquecer por ID si existe
                    a_id = a.get('id') or a.get('abono_id')
                    try:
                        if a_id:
                            a_full = self._get_abono_with_cache(a_id)
                            if a_full:
                                m_raw = self._obtener_metodo_pago(a_full)
                                m_norm = self._normalizar_texto(m_raw).lower()
                                a = a_full
                    except Exception:
                        pass
                coincide_efectivo = ('efectivo' in metodo_norm and 'efectivo' in m_norm)
                coincide_consig = ('consignacion' in metodo_norm and 'consignacion' in m_norm)
                if coincide_efectivo or coincide_consig:
                    cliente = self._extract_cliente_nombre(a)
                    if not cliente:
                        # Intentar enriquecer con tarjeta si aún vacío
                        t_codigo = self._get_tarjeta_codigo_from_data(a)
                        t_id = self._get_tarjeta_id_from_data(a)
                        t_full = self._get_tarjeta_with_cache(codigo=t_codigo, tarjeta_id=t_id)
                        if t_full:
                            cliente = self._extract_cliente_nombre(t_full)
                    abonado = self._first_number(a, ('monto', 'valor'))
                    filas.append((cliente or '—', f"$ {abonado:,.0f}"))
                    raw_filtrados.append(a)
            ctx = 'efectivo' if 'efectivo' in metodo_norm else 'consignacion'
            self._mostrar_tabla_detalle(titulo, columnas, filas, raw_items=raw_filtrados, contexto=ctx)
        except Exception as e:
            logger.error(f"Error al cargar detalle por método {metodo}: {e}")
            messagebox.showerror("Error", f"No se pudo cargar el detalle por método: {e}")

    def actualizar_interfaz_base(self):
        """Actualiza la interfaz de base según si ya existe una base asignada, usando la API."""
        if not self.empleado_actual_id:
            self.mostrar_interfaz_sin_empleado()
            return
            
        try:
            fecha_str = self.fecha_actual.strftime('%Y-%m-%d')
            base_existente = self.api_client.get_base_by_empleado_fecha(self.empleado_actual_id, fecha_str)

            # Tratar None como caso normal: no hay base asignada aún para ese día
            if base_existente:
                self.mostrar_interfaz_base_existente(base_existente)
            else:
                self.mostrar_interfaz_asignar_base()

        except Exception as e:
            # Cualquier otro error distinto a "no existe" debe considerarse error real de interfaz
            logger.error(f"Error al actualizar interfaz de base desde API: {e}")
            self.mostrar_interfaz_error()

    def limpiar_contenido_base(self):
        """Limpia el contenido actual del frame de base"""
        for widget in self.base_content_frame.winfo_children():
            widget.destroy()

    def mostrar_interfaz_sin_empleado(self):
        """Muestra mensaje cuando no hay empleado seleccionado"""
        self.limpiar_contenido_base()
        self.base_frame.config(text="💰 Base del Día")
        
        ttk.Label(self.base_content_frame, 
                text="Seleccione un empleado para gestionar la base", 
                font=('Segoe UI', 9)).pack(pady=5)

    def mostrar_interfaz_asignar_base(self):
        """Muestra interfaz para asignar nueva base"""
        self.limpiar_contenido_base()
        self.base_frame.config(text="💰 Asignar Base del Día")
        
        # Mensaje informativo
        info_frame = ttk.Frame(self.base_content_frame)
        info_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(info_frame, text="No hay base asignada para este día", 
                font=('Segoe UI', 9), foreground='#F59E0B').pack()
        
        # Frame para entrada y botón
        input_frame = ttk.Frame(self.base_content_frame)
        input_frame.pack(fill='x', pady=5)
        
        ttk.Label(input_frame, text="Monto Base:", font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        entry_frame = ttk.Frame(input_frame)
        entry_frame.pack(fill='x', pady=(5, 10))
        
        ttk.Label(entry_frame, text="$", font=('Segoe UI', 10)).pack(side='left')
        
        self.entry_nueva_base = ttk.Entry(entry_frame, width=12, font=('Segoe UI', 10))
        self.entry_nueva_base.pack(side='left', padx=(2, 0))
        self.entry_nueva_base.bind('<Return>', lambda e: self.asignar_base_rapida())
        
        # Botón de asignar
        self.btn_asignar_base = tk.Button(input_frame, text="✅ Asignar Base",
                                        bg='#10B981', fg='white', font=('Segoe UI', 10, 'bold'),
                                        command=self.asignar_base_rapida)
        self.btn_asignar_base.pack(fill='x', pady=(5, 0))
        
        # Mensaje adicional
        ttk.Label(self.base_content_frame,
                text="💡 Tip: También puede gestionar bases en la pestaña 'Empleado'",
                font=('Segoe UI', 8), foreground='#6B7280').pack(pady=(10, 0))

    def mostrar_interfaz_base_existente(self, base_data: Dict):
        """Muestra interfaz cuando ya existe una base asignada"""
        self.limpiar_contenido_base()
        self.base_frame.config(text="💰 Base del Día - Asignada")
        
        # Estado de la base
        status_frame = ttk.Frame(self.base_content_frame)
        status_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(status_frame, text="✅ Base asignada correctamente", 
                font=('Segoe UI', 9), foreground='#059669').pack()
        
        # Frame para mostrar base actual
        display_frame = ttk.Frame(self.base_content_frame)
        display_frame.pack(fill='x', pady=5)
        
        ttk.Label(display_frame, text="Monto de la Base:", font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        monto = Decimal(base_data.get('monto', 0))
        monto_frame = ttk.Frame(display_frame)
        monto_frame.pack(fill='x', pady=(5, 15))
        
        lbl_monto = ttk.Label(monto_frame, text=f"$ {monto:,.0f}", 
                            font=('Segoe UI', 14, 'bold'), foreground='#059669')
        lbl_monto.pack()
        
        # Información adicional usando la fecha de la base
        fecha_base = base_data.get('fecha')
        try:
            if isinstance(fecha_base, str):
                fecha_dt = datetime.fromisoformat(fecha_base)
            else:
                fecha_dt = fecha_base
            fecha_formateada = fecha_dt.strftime('%d/%m/%Y') if fecha_dt else 'No disponible'
        except Exception:
            fecha_formateada = 'No disponible'

        ttk.Label(display_frame, text=f"Fecha: {fecha_formateada}", 
                font=('Segoe UI', 8), foreground='#6B7280').pack(pady=(0, 10))
        
        # Botón para ir a gestión completa
        btn_gestionar = tk.Button(display_frame, text="⚙️ Gestionar en Pestaña Empleado",
                                bg='#6366F1', fg='white', font=('Segoe UI', 10, 'bold'),
                                command=self.abrir_gestion_empleado)
        btn_gestionar.pack(fill='x', pady=(5, 0))
        
        # Mensaje informativo
        ttk.Label(self.base_content_frame,
                text="💡 Para modificar o eliminar la base, use la pestaña 'Empleado'",
                font=('Segoe UI', 8), foreground='#6B7280').pack(pady=(10, 0))

    def mostrar_interfaz_error(self):
        """Muestra interfaz de error"""
        self.limpiar_contenido_base()
        self.base_frame.config(text="💰 Base del Día - Error")
        
        ttk.Label(self.base_content_frame,
                text="❌ Error al cargar información de base",
                font=('Segoe UI', 9), foreground='#EF4444').pack(pady=5)

    def asignar_base_rapida(self):
        """Asigna una base al empleado para el día (atajo rápido) usando la API."""
        if not self.empleado_actual_id:
            messagebox.showwarning("Advertencia", "Seleccione un empleado")
            return
        
        try:
            monto_str = self.entry_nueva_base.get().strip()
            if not monto_str:
                messagebox.showwarning("Advertencia", "Ingrese el monto de la base")
                return
            
            monto = Decimal(monto_str.replace(',', '').replace('$', ''))
            if monto <= 0:
                messagebox.showwarning("Advertencia", "El monto debe ser mayor a cero")
                return

            base_data = {
                "empleado_id": self.empleado_actual_id,
                "fecha": self.fecha_actual.strftime('%Y-%m-%d'),
                "monto": float(monto) # La API espera un float
            }

            nueva_base = self.api_client.create_base(base_data)

            if nueva_base and 'id' in nueva_base:
                messagebox.showinfo("Éxito", f"Base de $ {monto:,.0f} asignada correctamente")
                # Esta actualización SÍ es necesaria porque se asignó una nueva base
                self.actualizar_liquidacion()
            else:
                error_msg = nueva_base.get('detail', 'Error desconocido')
                # Si el error es por base duplicada, mostramos un mensaje amigable
                if "ya tiene una base" in str(error_msg):
                     messagebox.showwarning("Advertencia", 
                                     "Ya existe una base para este día. La interfaz se actualizará.")
                     self.actualizar_interfaz_base()
                else:
                    messagebox.showerror("Error", f"No se pudo asignar la base: {error_msg}")
                
        except ValueError:
            messagebox.showerror("Error", "Monto inválido. Ingrese solo números")
        except Exception as e:
            logger.error(f"Error al asignar base rápida vía API: {e}")
            messagebox.showerror("Error de API", f"Error al asignar base: {e}")

    def abrir_gestion_empleado(self):
        """Muestra mensaje para dirigir al frame de empleado"""
        empleado_nombre = self.combo_empleado.get() if hasattr(self, 'combo_empleado') else "empleado"
        fecha_str = self.fecha_actual.strftime('%d/%m/%Y')
        
        mensaje = (f"Para gestionar completamente la base del empleado '{empleado_nombre}' "
                  f"para la fecha {fecha_str}:\n\n"
                  f"1. Vaya a la pestaña 'Empleado'\n"
                  f"2. Seleccione el empleado en la lista\n"
                  f"3. Use la sección 'Base del día' donde puede:\n"
                  f"   • Buscar bases existentes\n"
                  f"   • Agregar nuevas bases\n"
                  f"   • Actualizar bases existentes\n"
                  f"   • Eliminar bases\n"
                  f"   • Buscar por cualquier fecha")
        
        messagebox.showinfo("Gestión Completa de Bases", mensaje) 

    # Utilidades
    def _obtener_metodo_pago(self, abono: Dict) -> str:
        """Obtiene el valor del método de pago desde varias posibles claves."""
        try:
            for key in (
                'metodo_pago', 'metodo', 'forma_pago',
                'metodoPago', 'metodoDePago', 'payment_method'
            ):
                value = abono.get(key)
                if value is not None and str(value).strip() != "":
                    return str(value)
        except Exception:
            pass
        return ""

    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto removiendo acentos/diacríticos para comparaciones robustas."""
        if not texto:
            return ""
        try:
            texto_str = str(texto)
            texto_nfd = unicodedata.normalize('NFD', texto_str)
            return ''.join(c for c in texto_nfd if unicodedata.category(c) != 'Mn')
        except Exception:
            return str(texto)

    def _first_number(self, data: dict, key_candidates: tuple) -> Decimal:
        """Devuelve el primer valor numérico encontrado entre varias claves, como Decimal."""
        for key in key_candidates:
            value = data.get(key)
            if value is None:
                continue
            try:
                return Decimal(str(value))
            except Exception:
                continue
        return Decimal(0)

    def _parse_iso_date_only(self, fecha) -> str:
        """Convierte ISO o tipo datetime a 'dd/mm/YYYY' sin hora."""
        if not fecha:
            return ""
        try:
            if isinstance(fecha, str):
                dt = datetime.fromisoformat(str(fecha).replace('Z', '+00:00'))
            else:
                dt = fecha
            return dt.strftime('%d/%m/%Y')
        except Exception:
            return str(fecha)

    def _extraer_monto_prestamo_de_abono(self, abono: dict):
        """Intenta extraer el monto del préstamo asociado al abono, si está disponible."""
        try:
            for key in ('monto_prestamo', 'monto_tarjeta', 'tarjeta_monto'):
                if key in abono:
                    return Decimal(str(abono.get(key)))
            tarjeta = abono.get('tarjeta') or {}
            for key in ('monto', 'monto_prestamo'):
                if key in tarjeta:
                    return Decimal(str(tarjeta.get(key)))
        except Exception:
            return None
        return None

    def _get_tarjeta_codigo_from_data(self, data: dict) -> str:
        """Intenta extraer el código de tarjeta desde varias claves posibles."""
        try:
            for key in (
                'tarjeta_codigo', 'codigo_tarjeta', 'codigo', 'tarjetaCodigo'
            ):
                val = data.get(key)
                if val is not None and str(val).strip() != "":
                    return str(val)
            # También desde anidado 'tarjeta'
            tarjeta = data.get('tarjeta') or {}
            if isinstance(tarjeta, dict):
                val = tarjeta.get('codigo') or tarjeta.get('tarjeta_codigo')
                if val:
                    return str(val)
        except Exception:
            pass
        return ""

    def _get_tarjeta_id_from_data(self, data: dict):
        """Intenta extraer el ID de la tarjeta desde varias claves posibles."""
        try:
            for key in ('tarjeta_id', 'id_tarjeta', 'idTarjeta'):
                val = data.get(key)
                if val is not None and str(val).strip() != "":
                    return val
            tarjeta = data.get('tarjeta') or {}
            if isinstance(tarjeta, dict):
                val = tarjeta.get('id') or tarjeta.get('tarjeta_id')
                if val is not None:
                    return val
        except Exception:
            pass
        return None

    def _try_fetch_tarjeta(self, codigo: str = None, tarjeta_id=None):
        """Intenta obtener datos de tarjeta por código o ID usando varias rutas del cliente API."""
        try:
            if codigo:
                try:
                    return self.api_client.get_tarjeta_by_codigo(codigo)
                except Exception:
                    pass
            if tarjeta_id is not None:
                try:
                    return self.api_client.get_tarjeta(int(tarjeta_id))
                except Exception:
                    pass
            if codigo and tarjeta_id is None:
                # último intento: algunos backends usan un único get_tarjeta para código
                try:
                    return self.api_client.get_tarjeta(codigo)
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def _extract_contacto_from_tarjeta(self, tarjeta: dict) -> tuple:
        """Extrae (telefono, direccion) desde tarjeta->cliente con múltiples claves fallback."""
        try:
            cliente = tarjeta.get('cliente') or {}
            telefono = (
                cliente.get('telefono') or cliente.get('celular') or cliente.get('telefono1') or
                tarjeta.get('cliente_telefono') or tarjeta.get('telefono_cliente') or tarjeta.get('telefono')
            )
            direccion = (
                cliente.get('direccion') or cliente.get('direccion_residencia') or
                tarjeta.get('cliente_direccion') or tarjeta.get('direccion_cliente') or tarjeta.get('direccion')
            )
            return str(telefono or ''), str(direccion or '')
        except Exception:
            return '', ''

    def _get_first_str(self, data: dict, key_candidates: tuple) -> str:
        """Devuelve el primer valor de texto encontrado entre varias claves."""
        for key in key_candidates:
            try:
                val = data.get(key)
            except Exception:
                val = None
            if val is not None and str(val).strip() != "":
                return str(val)
        return ""

    def _parse_iso_dt(self, fecha) -> datetime:
        """Parsea ISO (con Z o +00:00) o datetime a objeto datetime."""
        if not fecha:
            return None
        try:
            if isinstance(fecha, str):
                return datetime.fromisoformat(str(fecha).replace('Z', '+00:00').replace('z', '+00:00'))
            return fecha
        except Exception:
            return None

    def _build_abonos_index_por_tarjeta(self, fecha_str: str) -> dict:
        """Construye índice {codigo_tarjeta: abono_dict_ultimo_del_dia} para búsquedas rápidas."""
        index = {}
        try:
            items = self.api_client.list_abonos_del_dia(self.empleado_actual_id, fecha_str)
            for a in items:
                codigo = (
                    a.get('tarjeta_codigo') or a.get('codigo_tarjeta') or (
                        (a.get('tarjeta') or {}).get('codigo') if isinstance(a.get('tarjeta'), dict) else None
                    ) or a.get('tarjetaCodigo') or a.get('codigo')
                )
                if not codigo:
                    continue
                dt = self._parse_iso_dt(a.get('fecha') or a.get('created_at'))
                prev = index.get(codigo)
                if not prev:
                    index[codigo] = a
                else:
                    prev_dt = self._parse_iso_dt(prev.get('fecha') or prev.get('created_at'))
                    if (dt and not prev_dt) or (dt and prev_dt and dt > prev_dt):
                        index[codigo] = a
        except Exception:
            pass
        return index

    def _get_abono_with_cache(self, abono_id):
        try:
            if abono_id in self._abono_cache:
                return self._abono_cache[abono_id]
            ab = self.api_client.get_abono(int(abono_id))
            self._abono_cache[abono_id] = ab
            return ab
        except Exception:
            return None

    def _get_tarjeta_with_cache(self, codigo: str = None, tarjeta_id=None):
        key = (codigo or '') + '|' + (str(tarjeta_id) if tarjeta_id is not None else '')
        try:
            if key in self._tarjeta_cache:
                return self._tarjeta_cache[key]
            t = self._try_fetch_tarjeta(codigo=codigo, tarjeta_id=tarjeta_id)
            if t:
                self._tarjeta_cache[key] = t
            return t
        except Exception:
            return None

    def _refrescar_ventanas_detalle(self):
        try:
            # Cerrar y reabrir para forzar reconstrucción completa
            to_reopen = []
            for ctx, win in list(self._detalles_abiertos.items()):
                try:
                    if win and win.winfo_exists():
                        win.destroy()
                    to_reopen.append(ctx)
                except Exception:
                    pass
            # Limpiar registro
            self._detalles_abiertos.clear()
            # Reabrir según contexto
            for ctx in to_reopen:
                if ctx == 'abonos_dia':
                    self.mostrar_detalle_estadistica('total_registros')
                elif ctx == 'efectivo':
                    self.mostrar_detalle_recaudos_metodo('efectivo')
                elif ctx == 'consignacion':
                    self.mostrar_detalle_recaudos_metodo('consignacion')
                elif ctx == 'tarjetas_canceladas':
                    self.mostrar_detalle_estadistica('tarjetas_canceladas')
                elif ctx == 'tarjetas_nuevas':
                    self.mostrar_detalle_estadistica('tarjetas_nuevas')
        except Exception:
            pass

    def _extract_cliente_nombre(self, data: dict) -> str:
        """Construye 'APELLIDO NOMBRE' desde varias estructuras posibles en data.
        Busca en nivel actual, en 'cliente' y en 'tarjeta'->'cliente'."""
        try:
            # Nivel actual
            ap = str(data.get('cliente_apellido') or data.get('apellido') or '')
            no = str(data.get('cliente_nombre') or data.get('nombre') or '')
            if not (ap or no):
                # Subdict 'cliente'
                cli = data.get('cliente') or {}
                ap = str(cli.get('apellido') or ap or '')
                no = str(cli.get('nombre') or no or '')
            if not (ap or no):
                # Subdict 'tarjeta'->'cliente'
                tarj = data.get('tarjeta') or {}
                if isinstance(tarj, dict):
                    cli2 = tarj.get('cliente') or {}
                    ap = str(cli2.get('apellido') or ap or '')
                    no = str(cli2.get('nombre') or no or '')
            nombre = f"{ap} {no}".strip().upper()
            return nombre
        except Exception:
            return ""