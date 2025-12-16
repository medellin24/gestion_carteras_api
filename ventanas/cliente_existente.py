import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from api_client.client import api_client
from ventanas.nueva_tarjeta import VentanaNuevaTarjeta

class VentanaClienteExistente(tk.Toplevel):
    def __init__(self, parent, cliente):
        super().__init__(parent)
        self.parent = parent
        self.cliente = cliente
        # Cliente API para reusar token/autenticación
        self.api_client = api_client
        
        # Configurar ventana
        self.title("Cliente Existente")
        self.geometry("800x600")
        self.resizable(False, False)
        
        # Centrar la ventana
        self.center_window()
        
        # Hacer la ventana modal
        self.transient(parent)
        self.grab_set()
        
        # Configurar la interfaz
        self.setup_ui()
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_ui(self):
        """Interfaz para cliente existente con historial"""
        # Frame principal con padding
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # IMPORTANTE: Los botones se agregan PRIMERO con side='bottom' 
        # para que siempre estén visibles, sin importar el contenido superior
        frame_botones = ttk.Frame(main_frame)
        frame_botones.pack(side='bottom', fill='x', pady=(20, 0))
        
        ttk.Button(frame_botones, text="CREAR", width=15, padding=5,
                   command=self.crear_nueva_tarjeta).pack(side='left', padx=5)
        ttk.Button(frame_botones, text="CANCELAR", width=15, padding=5,
                   command=self.destroy).pack(side='right', padx=5)
        
        # Sección Cliente (ahora se agrega después de los botones)
        cliente_frame = ttk.LabelFrame(main_frame, text="Cliente", padding="10")
        cliente_frame.pack(fill='x', pady=(0, 10))
        
        # Datos personales
        ttk.Label(cliente_frame, text=f"{self.cliente['nombre']} {self.cliente['apellido']}").grid(
            row=0, column=0, sticky='w', columnspan=2)
        ttk.Label(cliente_frame, text=f"ID: {self.cliente['identificacion']}").grid(
            row=1, column=0, sticky='w')
        
        if self.cliente.get('telefono'):
            ttk.Label(cliente_frame, text=f"Tel: {self.cliente['telefono']}").grid(
                row=1, column=1, sticky='w', padx=(20,0))
        
        if self.cliente.get('direccion'):
            ttk.Label(cliente_frame, text=f"Dir: {self.cliente['direccion']}").grid(
                row=2, column=0, sticky='w', columnspan=2)
        
        # Estadísticas
        stats = api_client.get_cliente_estadisticas(self.cliente['identificacion'])
        
        ttk.Label(cliente_frame, text=f"Cantidad: {stats['cantidad_tarjetas']}").grid(
            row=3, column=0, sticky='w', pady=(10,0))
        ttk.Label(cliente_frame, text=f"Total: ${stats['total_prestado']:,.0f}").grid(
            row=3, column=1, sticky='w', padx=(20,0), pady=(10,0))
        
        # Botón Data Crédito
        ttk.Button(cliente_frame, text="DATA CREDITO", 
                   command=self.consultar_data_credito).grid(
            row=4, column=0, sticky='w', pady=(10,0))
        
        # Historial de tarjetas (se expande en el espacio restante)
        self.setup_historial(main_frame)

    def setup_historial(self, parent_frame):
        """Configura la sección de historial"""
        historial_frame = ttk.LabelFrame(parent_frame, text="Historial de tarjetas", padding="10")
        historial_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        # Crear Treeview
        columns = ('fecha', 'monto', 'estado', 'saldo', 'dias', 'empleado')
        self.tree = ttk.Treeview(historial_frame, columns=columns, show='headings', height=10)
        
        # Configurar columnas
        self.tree.heading('fecha', text='Fecha')
        self.tree.heading('monto', text='Monto')
        self.tree.heading('estado', text='Estado')
        self.tree.heading('saldo', text='Saldo')
        self.tree.heading('dias', text='Días')
        self.tree.heading('empleado', text='Empleado')
        
        # Cargar datos del historial
        self.cargar_historial()
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(historial_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Posicionar elementos
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def cargar_historial(self):
        """Carga el historial de tarjetas del cliente"""
        historial = api_client.get_cliente_historial(self.cliente['identificacion'])
        for tarjeta in historial:
            try:
                dias = tarjeta['dias_atrasados']
                tag = 'atrasado' if dias > 0 else 'adelantado'
                # Formatear fecha robustamente (acepta date/datetime o ISO string)
                fecha_val = tarjeta.get('fecha_creacion')
                if hasattr(fecha_val, 'strftime'):
                    fecha_fmt = fecha_val.strftime('%d/%m/%Y')
                elif isinstance(fecha_val, str):
                    try:
                        if 'T' in fecha_val:
                            fecha_fmt = datetime.fromisoformat(fecha_val.replace('Z', '+00:00')).strftime('%d/%m/%Y')
                        else:
                            fecha_fmt = datetime.strptime(fecha_val, '%Y-%m-%d').strftime('%d/%m/%Y')
                    except Exception:
                        fecha_fmt = fecha_val
                else:
                    fecha_fmt = ''
                
                self.tree.insert('', 'end', values=(
                    fecha_fmt,
                    f"${tarjeta['monto_total']:,.0f}",
                    tarjeta['estado'],
                    f"${tarjeta['monto_total']:,.0f}",
                    dias,
                    tarjeta['empleado']
                ), tags=(tag,))
            except Exception as e:
                print(f"Error al insertar tarjeta en historial: {e}")
        
        # Configurar colores
        self.tree.tag_configure('atrasado', foreground='red')
        self.tree.tag_configure('adelantado', foreground='green')

    def consultar_data_credito(self):
        """Consulta el historial crediticio del cliente"""
        try:
            ident = self.cliente.get('identificacion')
            if not ident:
                messagebox.showerror("Error", "No se encontró la identificación del cliente.")
                return
            # Reusar el token de la sesión actual (si existe)
            token = getattr(self.api_client.config, 'auth_token', None)
            # URL base de producción (PWA) para abrir DataCrédito directamente.
            base_url = "https://gestion-carteras-api.pages.dev"
            url = f"{base_url}/datacredito/{ident}"
            if token:
                try:
                    from urllib.parse import urlencode
                    url += "?" + urlencode({"token": token})
                except Exception:
                    url += f"?token={token}"
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir DataCrédito: {e}")

    def crear_nueva_tarjeta(self):
        """Abre la ventana de nueva tarjeta con los datos del cliente"""
        self.destroy()
        VentanaNuevaTarjeta(self.parent, cliente=self.cliente) 