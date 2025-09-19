import tkinter as tk
from tkinter import ttk, messagebox

# Las importaciones ahora son directas, sin el prefijo del paquete anterior
from frames.frame_entrega import FrameEntrega
from frames.frame_liquidacion import FrameLiquidacion
from frames.frame_empleado import FrameEmpleado
from frames.frame_finanzas import FrameFinanzas
from api_client.client import api_client, APIError

class VentanaPrincipal:
    def __init__(self, root):
        self.root = root
        self.root.title("SIRC [nombre propietario] tiempo:[0] 37x.gg")
        self.root.geometry("1200x700")  # Ajusta según necesites
        
        # ✅ OPTIMIZACIÓN: Cache de frames para reutilización
        self.frames_cache = {}
        self.frame_actual = None
        
        # EL CACHÉ DE EMPLEADOS SE ELIMINA. CADA FRAME GESTIONA SUS DATOS.
        
        # Crear la estructura principal (orden corregido)
        self.crear_menu()
        self.crear_botones_principales()
        self.crear_barra_estado()  # ✅ Crear ANTES del contenedor
        self.crear_contenedor_frames()
        
    def crear_menu(self):
        """Crear barra de menú superior"""
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        # Menú Archivo
        archivo_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Archivo", menu=archivo_menu)
        archivo_menu.add_command(label="Salir", command=self.root.quit)
        
        # Otros menús
        self.menu_bar.add_cascade(label="Perfil")
        self.menu_bar.add_cascade(label="Vista")
        self.menu_bar.add_cascade(label="Herramientas")
        self.menu_bar.add_cascade(label="Ayuda")
        
        # Licencia (como label interactivo)
        self.lic_label = tk.Menu(self.menu_bar, tearoff=0)
        # Insertar comando placeholder y guardar su índice para poder actualizarlo luego
        self.menu_bar.add_command(label="Licencia: [cargando]", command=self.mostrar_detalle_licencia)
        self._licencia_menu_index = self.menu_bar.index('end')
        # Iniciar actualización y refresco periódico del estado de licencia
        self._iniciar_actualizacion_licencia()
    
    def crear_botones_principales(self):
        """Crear botones principales"""
        self.frame_botones = ttk.Frame(self.root)
        self.frame_botones.pack(fill='x', padx=5, pady=5)
        
        # Estilo para los botones
        style = ttk.Style()
        style.configure('Principal.TButton', padding=10)
        
        # Crear botones
        self.btn_entrega = ttk.Button(self.frame_botones, text="Entrega", 
                                    style='Principal.TButton', command=self.mostrar_entrega)
        self.btn_liquidacion = ttk.Button(self.frame_botones, text="Liquidación", 
                                        style='Principal.TButton', command=self.mostrar_liquidacion)
        self.btn_empleado = ttk.Button(self.frame_botones, text="Empleado", 
                                     style='Principal.TButton', command=self.mostrar_empleado)
        self.btn_finanzas = ttk.Button(self.frame_botones, text="Finanzas (En desarrollo)", 
                                     style='Principal.TButton', command=self.mostrar_finanzas)
        
        # Desactivar el botón de Finanzas temporalmente
        self.btn_finanzas.config(state=tk.DISABLED)
        
        # Ubicar botones
        self.btn_entrega.pack(side='left', padx=5)
        self.btn_liquidacion.pack(side='left', padx=5)
        self.btn_empleado.pack(side='left', padx=5)
        self.btn_finanzas.pack(side='left', padx=5)
    
    def crear_contenedor_frames(self):
        """Crear contenedor para los frames principales"""
        self.contenedor = ttk.Frame(self.root)
        self.contenedor.pack(fill='both', expand=True, padx=5, pady=5)
        
        # ✅ Mostrar frame inicial (Entrega)
        self.mostrar_entrega()
    
    def crear_barra_estado(self):
        """Crear barra de estado inferior"""
        self.barra_estado = ttk.Label(self.root, text="Finalizado.", relief=tk.SUNKEN)
        self.barra_estado.pack(side='bottom', fill='x')

    def _iniciar_actualizacion_licencia(self):
        """Configura la primera actualización inmediata y un refresco diario (una vez al día)."""
        # Evitar iniciar múltiples timers
        if getattr(self, '_lic_timer_started', False):
            return
        self._lic_timer_started = True
        # Actualización inmediata
        self._actualizar_menu_licencia()
        # Programar el siguiente refresco al próximo cambio de día (medianoche local)
        try:
            self.root.after(self._ms_hasta_proximo_dia(), self._programar_refresco_licencia)
        except Exception:
            # En caso de que no exista after (entornos de prueba), ignorar
            pass

    def _programar_refresco_licencia(self):
        """Refresca el menú de licencia y vuelve a programar el próximo refresco (diario)."""
        self._actualizar_menu_licencia()
        try:
            # Volver a programar para el siguiente cambio de día
            self.root.after(self._ms_hasta_proximo_dia(), self._programar_refresco_licencia)
        except Exception:
            pass

    def _actualizar_menu_licencia(self):
        """Obtiene los límites de cuenta y actualiza el texto del menú de licencia de forma robusta."""
        try:
            limits = api_client.get_admin_limits()
        except Exception:
            # Si falla, mostrar estado desconocido
            try:
                self.menu_bar.entryconfig(self._licencia_menu_index, label="Licencia: [sin conexión]")
            except Exception:
                pass
            return

        dias = int(limits.get('days_remaining', 0) or 0)
        es_trial = bool(limits.get('trial', False))
        estado = "Vencida" if dias <= 0 else ("Trial" if es_trial else "Plan")
        etiqueta = f"{estado}: [{dias} d]" if dias > 0 else f"{estado}"
        try:
            self.menu_bar.entryconfig(self._licencia_menu_index, label=etiqueta)
        except Exception:
            pass

    def _ms_hasta_proximo_dia(self):
        """Calcula milisegundos hasta la próxima medianoche local para refrescar una vez al día."""
        try:
            from datetime import datetime, timedelta
            now = datetime.now()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            delta_ms = int((tomorrow - now).total_seconds() * 1000)
            # Fallback mínimo de 1 minuto por seguridad
            return max(delta_ms, 60_000)
        except Exception:
            # Si algo falla, usar 24 horas
            return 24 * 60 * 60 * 1000

    def mostrar_detalle_licencia(self):
        """Muestra un modal con detalles de suscripción y uso del plan."""
        try:
            limits = api_client.get_admin_limits()
        except APIError as e:
            messagebox.showerror("Error", f"No se pudo obtener la información de la cuenta:\n{e.message}")
            return
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo obtener la información de la cuenta:\n{e}")
            return

        dias = limits.get('days_remaining', 0)
        max_emp = limits.get('max_empleados', 0)
        usados = limits.get('usados', 0)
        inact = limits.get('cobradores_inactivos', 0)
        disp = limits.get('disponibles', 0)
        es_trial = bool(limits.get('trial', False))
        estado = "Vencida" if (dias or 0) <= 0 else ("Trial" if es_trial else "Plan activo")

        top = tk.Toplevel(self.root)
        top.title("Detalle de Suscripción")
        top.geometry("400x260")
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()
        try:
            top.update_idletasks()
            x = (top.winfo_screenwidth() // 2) - (400 // 2)
            y = (top.winfo_screenheight() // 2) - (260 // 2)
            top.geometry("400x260+%d+%d" % (x, y))
        except Exception:
            pass

        cont = ttk.Frame(top, padding=20)
        cont.pack(fill='both', expand=True)

        ttk.Label(cont, text=f"Estado: {estado}", font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(cont, text=f"Días restantes: {dias}").pack(anchor='w')
        ttk.Label(cont, text=f"Cobradores del plan: {max_emp}").pack(anchor='w', pady=(8,0))
        ttk.Label(cont, text=f"Activos: {usados}").pack(anchor='w')
        ttk.Label(cont, text=f"Inactivos: {inact}").pack(anchor='w')
        ttk.Label(cont, text=f"Disponibles: {disp}").pack(anchor='w')

        # Mostrar empleados con cobrador activo
        try:
            cobradores_activos = api_client.get_cobradores_activos()
            if cobradores_activos.get('cobradores_activos'):
                ttk.Separator(cont, orient='horizontal').pack(fill='x', pady=(8,0))
                ttk.Label(cont, text="Empleados con cobrador activo:", font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(8,4))
                for cobrador in cobradores_activos['cobradores_activos']:
                    ttk.Label(cont, text=f"• {cobrador['nombre_completo']} ({cobrador['username']})", 
                             font=('Segoe UI', 9)).pack(anchor='w', padx=(16,0))
        except Exception:
            pass

        # Botón para refrescar límites en caliente
        def refrescar():
            try:
                nuevos = api_client.get_admin_limits()
            except Exception as ex:
                messagebox.showerror("Error", f"No se pudo refrescar: {ex}")
                return
            try:
                cont.destroy()
            except Exception:
                pass
            top.destroy()
            # Reabrir con datos frescos
            self.mostrar_detalle_licencia()

        ttk.Separator(cont, orient='horizontal').pack(fill='x', pady=12)
        if (dias or 0) <= 0:
            msg = "Su suscripción ha vencido. Por favor contacte al administrador para renovar."
            color = '#DC2626'
        elif es_trial:
            msg = "Periodo de prueba activo. Disfrute de todas las funciones durante el trial."
            color = '#2563EB'
        else:
            msg = "Suscripción vigente."
            color = '#059669'
        ttk.Label(cont, text=msg, foreground=color).pack(anchor='w')

        btns = ttk.Frame(cont)
        btns.pack(fill='x', pady=(15,0))
        
        # Botón de renovación si está vencida
        if (dias or 0) <= 0:
            ttk.Button(btns, text="Renovar suscripción", 
                       command=lambda: self.renovar_suscripcion(top)).pack(side='left', padx=(0,5))
        # Botón para activar disponibles si hay cupos
        elif disp > 0:
            ttk.Button(btns, text=f"Activar {disp} disponibles", 
                       command=lambda: self.activar_disponibles(top)).pack(side='left', padx=(0,5))
        
        ttk.Button(btns, text="Refrescar", command=refrescar).pack(side='left', padx=(0,5))
        ttk.Button(btns, text="Cerrar", command=top.destroy).pack(side='right')

    def renovar_suscripcion(self, parent_window):
        """Abre ventana para renovar suscripción."""
        from tkinter import simpledialog
        
        # Ventana simple para renovar
        max_emp = simpledialog.askinteger("Renovar Suscripción", 
                                         "Número de usuarios cobrador:", 
                                         initialvalue=1, minvalue=1, parent=parent_window)
        if max_emp is None:
            return
            
        dias = simpledialog.askinteger("Renovar Suscripción", 
                                      "Días de duración:", 
                                      initialvalue=30, minvalue=1, parent=parent_window)
        if dias is None:
            return
        
        try:
            result = api_client.renew_subscription(max_emp, dias, es_renovacion=True)
            messagebox.showinfo("Éxito", result["mensaje"], parent=parent_window)
            # Refrescar la ventana de licencia
            parent_window.destroy()
            self.mostrar_detalle_licencia()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo renovar la suscripción:\n{e}", parent=parent_window)

    def activar_disponibles(self, parent_window):
        """Activa todos los usuarios cobrador disponibles."""
        try:
            result = api_client.activate_available_cobradores()
            messagebox.showinfo("Éxito", result["mensaje"], parent=parent_window)
            # Refrescar la ventana de licencia
            parent_window.destroy()
            self.mostrar_detalle_licencia()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron activar los usuarios:\n{e}", parent=parent_window)
    
    # --- SE ELIMINAN LOS MÉTODOS DE CACHÉ DE EMPLEADOS ---
    # get_empleados_cache
    # invalidar_cache_empleados
    
    def _cambiar_frame(self, nombre_frame, clase_frame):
        """Método genérico para cambiar frames con optimización"""
        try:
            # Actualizar barra de estado (con verificación de seguridad)
            if hasattr(self, 'barra_estado'):
                self.barra_estado.config(text=f"Cargando {nombre_frame}...")
                self.root.update()
            
            # ✅ OPTIMIZACIÓN: Ocultar frame actual si existe
            if self.frame_actual:
                self.frame_actual.pack_forget()
            
            # ✅ OPTIMIZACIÓN: Reutilizar frame si ya existe en cache
            if nombre_frame in self.frames_cache:
                frame = self.frames_cache[nombre_frame]
                
                # Refrescar datos si el frame lo soporta
                if hasattr(frame, 'refrescar_datos'):
                    frame.refrescar_datos()
            else:
                # ✅ OPTIMIZACIÓN: Crear frame solo la primera vez
                frame = clase_frame(self.contenedor)
                
                self.frames_cache[nombre_frame] = frame
            
            # Mostrar frame
            frame.pack(fill='both', expand=True)
            self.frame_actual = frame
            
            # Actualizar barra de estado
            if hasattr(self, 'barra_estado'):
                self.barra_estado.config(text=f"{nombre_frame} cargado.")
            
        except Exception as e:
            if hasattr(self, 'barra_estado'):
                self.barra_estado.config(text=f"Error al cargar {nombre_frame}")
            messagebox.showerror("Error", f"Error al cargar {nombre_frame}: {str(e)}")
    
    # ✅ MÉTODOS OPTIMIZADOS - Sin recrear frames
    def mostrar_entrega(self):
        """Muestra el frame de entrega (optimizado)"""
        self._cambiar_frame("Entrega", FrameEntrega)
    
    def mostrar_liquidacion(self):
        """Muestra el frame de liquidación (optimizado)"""
        self._cambiar_frame("Liquidación", FrameLiquidacion)
    
    def mostrar_empleado(self):
        """Muestra el frame de empleado (optimizado)"""
        self._cambiar_frame("Empleado", FrameEmpleado)
    
    def mostrar_finanzas(self):
        """Muestra el frame de finanzas (optimizado)"""
        self._cambiar_frame("Finanzas", FrameFinanzas)

