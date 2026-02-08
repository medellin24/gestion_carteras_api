import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
import logging

logger = logging.getLogger(__name__)

# Las importaciones ahora son directas, sin el prefijo del paquete anterior
from frames.frame_entrega import FrameEntrega
from frames.frame_liquidacion import FrameLiquidacion
from frames.frame_empleado import FrameEmpleado
from frames.frame_finanzas import FrameFinanzas
from frames.frame_contabilidad import FrameContabilidad
from api_client.client import api_client, APIError

class VentanaPrincipal:
    APP_VERSION = "2.1"

    def __init__(self, root, user_email=None):
        self.root = root
        self.user_email = user_email
        self.app_version = self.APP_VERSION
        self._update_info = {}
        # Formatear título con email del usuario
        if user_email:
            self.root.title(f"NeonBlue [{user_email}] informes : 3112027405")
        else:
            self.root.title("NeonBlue [usuario@ejemplo.com] informes : 3112027405")
        sw = self.root.winfo_screenwidth()
        x_offset = max((sw - 1200) // 2, 0)
        self.root.geometry(f"1200x700+{x_offset}+20")  # Ajusta según necesites y sitúa arriba
        # Fondo general gris claro para mayor contraste
        try:
            self.root.configure(bg="#ECEFF3")
        except Exception:
            pass
        
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

        # Botón volver a login
        self.menu_bar.add_command(label="Volver", command=self.volver_login)

        # Menú herramientas (se mantiene por si se agregan funciones más adelante)
        herramientas_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Herramientas", menu=herramientas_menu)

        # Ayuda
        self.menu_bar.add_command(label="Ayuda", command=self.mostrar_ayuda)

        # Licencia (como label interactivo)
        self.menu_bar.add_command(label="Licencia: [cargando]", command=self.mostrar_detalle_licencia)
        self._licencia_menu_index = self.menu_bar.index('end')
        self._aplicar_estilo_licencia()
        # Iniciar actualización y refresco periódico del estado de licencia
        self._iniciar_actualizacion_licencia()

        # Versión actual (se actualiza si hay nueva versión disponible)
        self.menu_bar.add_command(label=f"v{self.app_version}", state='disabled')
        self._version_menu_index = self.menu_bar.index('end')
        # Verificar actualizaciones en segundo plano
        self._verificar_actualizacion()

    def _aplicar_estilo_licencia(self):
        """Aplica estilo personalizado al menú de licencia."""
        try:
            self.menu_bar.entryconfig(self._licencia_menu_index, background='#B2FF59', activebackground='#9CE64D')
        except Exception:
            pass

    # --- Verificación de actualizaciones ---

    def _verificar_actualizacion(self):
        """Consulta la API en segundo plano para detectar nueva versión."""
        def _check():
            try:
                data = api_client.get_app_version()
                remote_version = data.get('version', '')
                if remote_version and remote_version != self.app_version:
                    self._update_info = data
                    self.root.after(0, self._mostrar_indicador_actualizacion)
            except Exception as e:
                logger.debug(f"No se pudo verificar actualización: {e}")
        threading.Thread(target=_check, daemon=True).start()

    def _mostrar_indicador_actualizacion(self):
        """Actualiza el menú para mostrar que hay una nueva versión disponible."""
        try:
            nueva = self._update_info.get('version', '?')
            self.menu_bar.entryconfig(
                self._version_menu_index,
                label=f"\u2b06 Nueva versión {nueva} disponible",
                state='normal',
                command=self._dialogo_actualizacion,
                background='#FF9800',
                foreground='#000000',
                activebackground='#F57C00',
            )
        except Exception as e:
            logger.debug(f"Error al mostrar indicador de actualización: {e}")

    def _dialogo_actualizacion(self):
        """Muestra diálogo con info de la nueva versión y botón de descarga."""
        info = self._update_info or {}
        nueva_version = info.get('version', '?')
        notas = info.get('notas', '')
        download_url = info.get('download_url', '')

        top = tk.Toplevel(self.root)
        top.title("Actualización disponible")
        top.geometry("420x220")
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()
        try:
            top.update_idletasks()
            x = (top.winfo_screenwidth() // 2) - (420 // 2)
            y = (top.winfo_screenheight() // 2) - (220 // 2)
            top.geometry(f"420x220+{x}+{y}")
        except Exception:
            pass

        cont = ttk.Frame(top, padding=20)
        cont.pack(fill='both', expand=True)

        ttk.Label(cont, text="Nueva versión disponible", font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        ttk.Label(cont, text=f"Versión instalada: {self.app_version}").pack(anchor='w', pady=(8, 0))
        ttk.Label(cont, text=f"Versión disponible: {nueva_version}", foreground='#2E7D32').pack(anchor='w')
        if notas:
            ttk.Label(cont, text=f"Notas: {notas}", wraplength=380).pack(anchor='w', pady=(6, 0))

        btn_frame = ttk.Frame(cont)
        btn_frame.pack(fill='x', pady=(16, 0))

        if download_url:
            ttk.Button(btn_frame, text="Descargar instalador", command=lambda: self._abrir_descarga(download_url, top)).pack(side='left')
        else:
            ttk.Label(btn_frame, text="Link de descarga no disponible aún", foreground='#999').pack(side='left')

        ttk.Button(btn_frame, text="Cerrar", command=top.destroy).pack(side='right')

    def _abrir_descarga(self, url, dialogo=None):
        """Abre el link de descarga en el navegador predeterminado."""
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el navegador:\n{e}")
        if dialogo:
            try:
                dialogo.destroy()
            except Exception:
                pass

    def mostrar_ayuda(self):
        """Mostrar información de soporte."""
        mensaje = (
            "Para contactar soporte al cliente comuníquese al correo: "
            "jorgeale17@hotmail.com o al número: +57 3112027405."
        )
        try:
            messagebox.showinfo("Ayuda", mensaje)
        except Exception:
            pass

    def volver_login(self):
        """Cerrar la ventana principal y volver a la pantalla de login."""
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            from main import main as run_main
            run_main()
        except Exception as e:
            print(f"Error al reiniciar aplicación: {e}")
    
    
    def crear_botones_principales(self):
        """Crear botones principales"""
        self.frame_botones = ttk.Frame(self.root, style='Nav.TFrame')
        self.frame_botones.pack(fill='x', padx=6, pady=2)

        # Estilos y tema para una apariencia moderna
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Nav.TFrame', background='#F7FAFC')
        style.configure('PrimaryNav.TButton', padding=4, font=('Segoe UI', 9, 'bold'))
        # Hover al azul bondi como los botones de Ver
        style.map('PrimaryNav.TButton', background=[('active', '#73D0E6')])

        # Usar grid para que los botones ocupen el ancho de la ventana con espacio entre ellos
        self.frame_botones.grid_columnconfigure(0, weight=1)
        self.frame_botones.grid_columnconfigure(1, weight=1)
        self.frame_botones.grid_columnconfigure(2, weight=1)
        self.frame_botones.grid_columnconfigure(3, weight=1)
        # Hacer el panel de navegación más angosto (más bajo)
        for btn in (0, 1, 2, 3):
            pass

        # Crear botones: Tarjetas, Liquidación, Rutas, Contabilidad
        self.btn_tarjetas = ttk.Button(self.frame_botones, text="Tarjetas", style='PrimaryNav.TButton', command=self.mostrar_entrega)
        self.btn_liquidacion = ttk.Button(self.frame_botones, text="Liquidación", style='PrimaryNav.TButton', command=self.mostrar_liquidacion)
        self.btn_rutas = ttk.Button(self.frame_botones, text="Rutas", style='PrimaryNav.TButton', command=self.mostrar_empleado)
        self.btn_contabilidad = ttk.Button(self.frame_botones, text="Contabilidad", style='PrimaryNav.TButton', command=self.mostrar_contabilidad)

        # Contabilidad ya está implementado - habilitado

        # Distribución horizontal con algo de espacio entre cada uno
        self.btn_tarjetas.grid(row=0, column=0, sticky='ew', padx=6)
        self.btn_liquidacion.grid(row=0, column=1, sticky='ew', padx=6)
        self.btn_rutas.grid(row=0, column=2, sticky='ew', padx=6)
        self.btn_contabilidad.grid(row=0, column=3, sticky='ew', padx=6)

        # (Separador removido por decisión de diseño)
    
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
            self._aplicar_estilo_licencia()
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

    def mostrar_contabilidad(self):
        """Muestra el frame de contabilidad"""
        self._cambiar_frame("Contabilidad", FrameContabilidad)

