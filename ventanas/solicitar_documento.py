import tkinter as tk
from tkinter import ttk, messagebox
from api_client.client import api_client

class VentanaSolicitarDocumento(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Documento Cliente")
        self.geometry("300x150")
        self.resizable(False, False)
        
        # Centrar la ventana
        self.center_window()
        
        # Configurar el foco en esta ventana
        self.focus_force()
        
        # Configurar la ventana como modal
        self.grab_set()
        
        self.setup_ui()
        
    def setup_ui(self):
        # Frame principal con padding
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Label
        ttk.Label(main_frame, text="Digite el documento del cliente:").pack(pady=(0, 10))
        
        # Entry con validación
        self.entry_documento = ttk.Entry(main_frame)
        self.entry_documento.pack(fill='x', pady=(0, 20))
        
        # Configurar validación
        vcmd = (self.register(self.validar_entrada), '%P')
        self.entry_documento.config(validate='key', validatecommand=vcmd)
        
        # Botón OK
        ttk.Button(main_frame, text="OK", command=self.verificar_cliente).pack()
        
        # Dar foco al entry
        self.entry_documento.focus_set()
        
        # Bind Enter key
        self.entry_documento.bind('<Return>', lambda e: self.verificar_cliente())
        
    def verificar_cliente(self):
        documento = self.entry_documento.get().strip()
        if not documento:
            messagebox.showwarning("Error", "Por favor ingrese un documento")
            return
            
        # Buscar cliente vía API
        try:
            cliente = api_client.get_cliente(documento)
        except Exception:
            cliente = None
        
        if cliente:
            # Cliente existe - mostrar ventana de cliente existente
            from ventanas.cliente_existente import VentanaClienteExistente
            self.destroy()
            VentanaClienteExistente(self.parent, cliente)
        else:
            # Cliente nuevo - mostrar ventana nueva tarjeta
            messagebox.showinfo("Cliente Nuevo", "Usuario no registrado")
            self.destroy()
            from ventanas.nueva_tarjeta import VentanaNuevaTarjeta
            VentanaNuevaTarjeta(self.parent, documento=documento)
        
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def validar_entrada(self, nuevo_valor):
        """Valida que solo se ingresen números y no más de 12 dígitos"""
        # Si está vacío, permitir (para poder borrar)
        if not nuevo_valor:
            return True
        
        # Verificar que sean solo números y no más de 12 dígitos
        if nuevo_valor.isdigit() and len(nuevo_valor) <= 12:
            return True
        
        return False 