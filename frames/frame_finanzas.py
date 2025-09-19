import tkinter as tk
from tkinter import ttk

class FrameFinanzas(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # Frame principal dividido en dos secciones
        self.frame_izquierdo = ttk.LabelFrame(self, text="Intervalo de fechas")
        self.frame_izquierdo.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        self.frame_derecho = ttk.LabelFrame(self, text="Información financiera")
        self.frame_derecho.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        self.setup_seccion_intervalo()
        self.setup_seccion_informacion()

    def setup_seccion_intervalo(self):
        # Frame para fechas
        frame_fechas = ttk.Frame(self.frame_izquierdo)
        frame_fechas.pack(fill='x', padx=5, pady=5)

        # Fecha inicial
        ttk.Label(frame_fechas, text="Fecha inicial:").pack(side='left', padx=5)
        self.entry_fecha_inicial = ttk.Entry(frame_fechas, width=15)
        self.entry_fecha_inicial.pack(side='left', padx=5)

        # Fecha final
        ttk.Label(frame_fechas, text="Fecha final:").pack(side='left', padx=5)
        self.entry_fecha_final = ttk.Entry(frame_fechas, width=15)
        self.entry_fecha_final.pack(side='left', padx=5)

        # Botones
        frame_botones = ttk.Frame(self.frame_izquierdo)
        frame_botones.pack(fill='x', padx=5, pady=5)

        self.btn_ver = ttk.Button(frame_botones, text="Ver", width=15)
        self.btn_ver.pack(side='left', padx=5)

        self.btn_limpiar = ttk.Button(frame_botones, text="Limpiar", width=15)
        self.btn_limpiar.pack(side='right', padx=5)

        # Área para mostrar el informe
        self.text_informe = tk.Text(self.frame_izquierdo, height=20)
        self.text_informe.pack(fill='both', expand=True, padx=5, pady=5)

    def setup_seccion_informacion(self):
        # Frame para etiquetas y valores
        frame_info = ttk.Frame(self.frame_derecho)
        frame_info.pack(fill='both', expand=True, padx=5, pady=5)

        # Botón Mostrar al inicio
        self.btn_mostrar = ttk.Button(frame_info, text="Mostrar", width=20)
        self.btn_mostrar.pack(anchor='w', pady=10)

        # Separador después del botón
        ttk.Separator(frame_info, orient='horizontal').pack(fill='x', pady=10)

        # Recaudo
        ttk.Label(frame_info, text="Recaudo:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        self.label_recaudo = ttk.Label(frame_info, text="$ 0")
        self.label_recaudo.pack(anchor='w', padx=20)

        # Gastos
        ttk.Label(frame_info, text="Gastos:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        self.label_gastos = ttk.Label(frame_info, text="$ 0")
        self.label_gastos.pack(anchor='w', padx=20)

        # Tarjetas
        ttk.Label(frame_info, text="Tarjetas:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        self.label_tarjetas = ttk.Label(frame_info, text="$ 0")
        self.label_tarjetas.pack(anchor='w', padx=20)

        # Total
        ttk.Label(frame_info, text="Total:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        self.label_total = ttk.Label(frame_info, text="$ 0")
        self.label_total.pack(anchor='w', padx=20)

        # Botón Gráfico
        self.btn_grafico = ttk.Button(self.frame_derecho, text="Gráfico", width=20)
        self.btn_grafico.pack(side='bottom', pady=20)