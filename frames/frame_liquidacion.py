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
        
        # Container principal con padding
        main_container = ttk.Frame(self, padding=15)
        main_container.pack(fill='both', expand=True)
        
        # SECCIÓN SUPERIOR: Selección de empleado y fecha
        header_frame = ttk.LabelFrame(main_container, text="Selección de Empleado y Fecha", padding=10)
        header_frame.pack(fill='x', pady=(0, 15))
        
        # Configurar grid del header
        header_frame.grid_columnconfigure(1, weight=1)
        header_frame.grid_columnconfigure(3, weight=1)
        
        # Empleado
        ttk.Label(header_frame, text="Empleado:", style='Header.TLabel').grid(
            row=0, column=0, sticky='w', padx=(0, 10))
        self.combo_empleado = ttk.Combobox(header_frame, width=30, state='readonly')
        self.combo_empleado.grid(row=0, column=1, sticky='ew', padx=(0, 20))
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
                                   width=12, 
                                   background='darkblue',
                                   foreground='white', 
                                   borderwidth=2,
                                   date_pattern='dd/mm/yyyy',
                                   locale='es_ES')
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
        stats_frame = ttk.LabelFrame(main_panel, text="Estadísticas de Tarjetas", padding=15)
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
            frame_row = ttk.Frame(stats_frame)
            frame_row.pack(fill='x', pady=8)
            
            ttk.Label(frame_row, text=texto, style='Header.TLabel').pack(side='left')
            
            lbl_valor = ttk.Label(frame_row, text="0", style='Value.TLabel')
            lbl_valor.pack(side='right')
            
            # Hacer clickeable solo para ciertas estadísticas (no tarjetas activas)
            if key != 'tarjetas_activas':
                lbl_valor.configure(cursor='hand2')
                lbl_valor.bind('<Button-1>', lambda e, stat_key=key: self.mostrar_detalle_estadistica(stat_key))
                # Efecto hover
                lbl_valor.bind('<Enter>', lambda e, lbl=lbl_valor: lbl.configure(foreground='#1E40AF'))
                lbl_valor.bind('<Leave>', lambda e, lbl=lbl_valor: lbl.configure(foreground='#2563EB'))
            
            self.labels_estadisticas[key] = lbl_valor
        
        # COLUMNA 2: Cálculos Financieros (la más ancha)
        calc_frame = ttk.LabelFrame(main_panel, text="Cálculos Financieros", padding=15)
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
            frame_row = ttk.Frame(calc_frame)
            frame_row.pack(fill='x', pady=8)
            
            ttk.Label(frame_row, text=texto, style='Header.TLabel').pack(side='left')
            
            lbl_valor = ttk.Label(frame_row, text="$ 0", style='Money.TLabel')
            lbl_valor.pack(side='right')
            
            self.labels_calculos[key] = lbl_valor

            # Agregar desglose bajo Total Recaudado
            if key == 'total_recaudado':
                # Efectivo
                fila_efectivo = ttk.Frame(calc_frame)
                fila_efectivo.pack(fill='x', pady=4, padx=(16, 0))
                ttk.Label(fila_efectivo, text="Efectivo:", style='Header.TLabel').pack(side='left')
                lbl_efectivo = ttk.Label(fila_efectivo, text="$ 0", style='Money.TLabel')
                lbl_efectivo.pack(side='right')
                self.labels_calculos['recaudado_efectivo'] = lbl_efectivo

                # Consignación
                fila_consig = ttk.Frame(calc_frame)
                fila_consig.pack(fill='x', pady=2, padx=(16, 0))
                ttk.Label(fila_consig, text="Consignación:", style='Header.TLabel').pack(side='left')
                lbl_consig = ttk.Label(fila_consig, text="$ 0", style='Money.TLabel')
                lbl_consig.pack(side='right')
                self.labels_calculos['recaudado_consignacion'] = lbl_consig
        
        # Línea separadora y total final
        ttk.Separator(calc_frame, orient='horizontal').pack(fill='x', pady=15)
        
        total_frame = ttk.Frame(calc_frame)
        total_frame.pack(fill='x', pady=10)
        
        ttk.Label(total_frame, text="TOTAL FINAL:", 
                font=('Segoe UI', 12, 'bold')).pack(side='left')
        
        lbl_total = ttk.Label(total_frame, text="$ 0", style='Total.TLabel')
        lbl_total.pack(side='right')
        self.labels_calculos['total_final'] = lbl_total

        # (Depuración eliminada)
        
        # COLUMNA 3: Gestión de Base
        base_frame = ttk.LabelFrame(main_panel, text="Gestión de Base", padding=15)
        base_frame.grid(row=0, column=2, sticky='nsew')
        
        # Frame para contenido dinámico de la base
        self.base_frame = base_frame
        self.base_content_frame = ttk.Frame(base_frame)
        self.base_content_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # Botón de generar liquidación (mismas dimensiones que asignar base)
        self.btn_generar_liquidacion = tk.Button(base_frame, text="💰 Generar Liquidación",
                                               bg='#10B981', fg='white', font=('Segoe UI', 10, 'bold'),
                                               command=self.generar_liquidacion)
        self.btn_generar_liquidacion.pack(fill='x', pady=10)
        
        # SECCIÓN INFERIOR: Gestión de Gastos (simplificada)
        gastos_frame = ttk.LabelFrame(main_container, text="Gestión de Gastos", padding=10)
        gastos_frame.pack(fill='both', expand=True)
        
        # Panel de control de gastos
        control_frame = ttk.Frame(gastos_frame)
        control_frame.pack(fill='x', pady=(0, 10))
        
        # Botones de gestión
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(side='left')
        
        self.btn_agregar_gasto = tk.Button(btn_frame, text="Agregar Gasto", 
                                         bg='#059669', fg='white', font=('Arial', 10, 'bold'),
                                         command=self.agregar_gasto_nuevo)
        self.btn_agregar_gasto.pack(side='left', padx=(0, 10))
        
        self.btn_editar_gasto = tk.Button(btn_frame, text="Editar", 
                                        bg='#F59E0B', fg='white', font=('Arial', 10, 'bold'),
                                        command=self.editar_gasto_seleccionado)
        self.btn_editar_gasto.pack(side='left', padx=(0, 10))
        
        self.btn_eliminar_gasto = tk.Button(btn_frame, text="Eliminar", 
                                          bg='#DC2626', fg='white', font=('Arial', 10, 'bold'),
                                          command=self.eliminar_gasto_seleccionado)
        self.btn_eliminar_gasto.pack(side='left')
        
        # Total de gastos del día
        total_gastos_frame = ttk.Frame(control_frame)
        total_gastos_frame.pack(side='right')
        
        ttk.Label(total_gastos_frame, text="Total Gastos:", 
                style='Header.TLabel').pack(side='left', padx=(0, 10))
        
        self.lbl_total_gastos_dia = ttk.Label(total_gastos_frame, text="$ 0", 
                                            style='Money.TLabel')
        self.lbl_total_gastos_dia.pack(side='right')
        
        # Tabla de gastos
        tree_frame = ttk.Frame(gastos_frame)
        tree_frame.pack(fill='both', expand=True)
        
        # Configurar Treeview
        columns = ('Tipo', 'Descripción', 'Valor')
        self.tree_gastos = ttk.Treeview(tree_frame, columns=columns, show='headings', height=8)
        
        # Configurar columnas
        self.tree_gastos.heading('Tipo', text='Tipo de Gasto')
        self.tree_gastos.heading('Descripción', text='Descripción')
        self.tree_gastos.heading('Valor', text='Valor')
        
        self.tree_gastos.column('Tipo', width=150)
        self.tree_gastos.column('Descripción', width=250)
        self.tree_gastos.column('Valor', width=100)
        
        # Scrollbar para la tabla
        scrollbar_gastos = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree_gastos.yview)
        self.tree_gastos.configure(yscrollcommand=scrollbar_gastos.set)
        
        # Empaquetar tabla y scrollbar
        self.tree_gastos.pack(side='left', fill='both', expand=True)
        scrollbar_gastos.pack(side='right', fill='y')
        
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
                cols = ("Código", "Cliente", "Ruta", "Monto")
                filas = [
                    (
                        t.get('codigo', ''),
                        f"{(t.get('cliente') or {}).get('apellido','').upper()} {(t.get('cliente') or {}).get('nombre','').upper()}".strip(),
                        str(t.get('numero_ruta', '')),
                        f"$ {Decimal(t.get('monto', 0)):,}"
                    ) for t in items
                ]
            elif tipo_estadistica == 'tarjetas_nuevas':
                items = self.api_client.list_tarjetas_nuevas_del_dia(self.empleado_actual_id, fecha_str)
                titulo = "Tarjetas nuevas del día"
                cols = ("Código", "Cliente", "Ruta", "Monto")
                filas = [
                    (
                        t.get('codigo', ''),
                        f"{(t.get('cliente') or {}).get('apellido','').upper()} {(t.get('cliente') or {}).get('nombre','').upper()}".strip(),
                        str(t.get('numero_ruta', '')),
                        f"$ {Decimal(t.get('monto', 0)):,}"
                    ) for t in items
                ]
            elif tipo_estadistica == 'total_registros':
                items = self.api_client.list_abonos_del_dia(self.empleado_actual_id, fecha_str)
                titulo = "Abonos del día"
                cols = ("ID", "Cliente", "Fecha", "Monto")
                filas = [
                    (
                        a.get('id', ''),
                        f"{str(a.get('cliente_apellido','') or '').upper()} {str(a.get('cliente_nombre','') or '').upper()}".strip(),
                        str(a.get('fecha', '')),
                        f"$ {Decimal(a.get('monto', 0)):,}"
                    ) for a in items
                ]
            else:
                messagebox.showinfo("Info", "Detalle no disponible para esta estadística.")
                return

            self._mostrar_tabla_detalle(titulo, cols, filas)
        except Exception as e:
            logger.error(f"Error al cargar detalle de {tipo_estadistica}: {e}")
            messagebox.showerror("Error", f"No se pudo cargar el detalle: {e}")

    def _mostrar_tabla_detalle(self, titulo, columnas, filas):
        ventana = tk.Toplevel(self)
        ventana.title(titulo)
        ventana.geometry("700x400")
        ventana.resizable(True, True)
        ventana.transient(self.winfo_toplevel())
        ventana.grab_set()
        try:
            ventana.update_idletasks()
            x = (ventana.winfo_screenwidth() // 2) - (700 // 2)
            y = (ventana.winfo_screenheight() // 2) - (400 // 2)
            ventana.geometry("700x400+%d+%d" % (x, y))
        except Exception:
            pass

        cont = ttk.Frame(ventana, padding=10)
        cont.pack(fill='both', expand=True)

        tree = ttk.Treeview(cont, columns=columnas, show='headings')
        for col in columnas:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        vs = ttk.Scrollbar(cont, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side='left', fill='both', expand=True)
        vs.pack(side='right', fill='y')

        for fila in filas:
            tree.insert('', 'end', values=fila)

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

    # (Depuración eliminada)